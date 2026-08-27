#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "status_card_packet.py"


def load_module():
    spec = importlib.util.spec_from_file_location("status_card_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def configure_temp_paths(module, root: Path) -> None:
    tmp = root / "tmp"
    state = root / "state"
    module.ROOT = root
    module.TMP = tmp
    module.STATE = state
    module.MEMORY = root / "memory"
    module.OUT = tmp / "veritas-status-card.json"
    module.FRONTDOOR_OUT = tmp / "veritas-status-card-frontdoor.json"
    module.STARTUP_PACKET = tmp / "startup-brief-packet.json"
    module.PM_PACKET = tmp / "pm-control-packet.json"
    module.CRON_PACKET = tmp / "cron-control-packet.json"
    module.FUTURE_PACKET = tmp / "future-session-enhancement-packet.json"
    module.TOKEN_USAGE_PACKET = tmp / "token-usage-ledger-current.json"
    module.TOKEN_BUDGET_PACKET = tmp / "token-budget-status.json"
    module.TMP_ARTIFACT_SPIRE_PACKET = tmp / "tmp-artifact-spire.json"
    module.SECURITY_WARNING_LEDGER_PACKET = tmp / "security-warning-ledger.json"
    module.CRON_FRESHNESS_SPINE_PACKET = tmp / "cron-freshness-spine.json"
    module.WF78_PROMOTION_VISIBILITY_PACKET = tmp / "wf78-promotion-visibility-top10.json"
    module.WF67_MANAGER_PACKET = tmp / "alpaca-paper-readiness" / "wf67-autonomous-paper-manager-current.json"
    module.WF67_PAPER_GUARD_PACKET = tmp / "alpaca-paper-readiness" / "paper-execution-guard-validation.json"
    module.SHADOW_ELIGIBILITY_PACKET = tmp / "paper-autotrader" / "shadow-eligibility.json"
    module.ARTIFACT_INDEX_DB = tmp / "veritas-artifact-index.sqlite"
    module.OWNER_GATED_PACKET = tmp / "owner-gated-action-review-queue.json"
    module.IMPROVEMENT_PACKET = tmp / "improvement-ledger-current.json"
    module.WF74_DECISION_DOCKET_PACKET = tmp / "wf74-decision-docket.json"
    module.OTEL_LEARNING_PACKET = tmp / "otel-learning-loop.json"
    module.WF88_WIKI_SYNTHESIS_PACKET = tmp / "wf88-wiki-synthesis-packet.json"
    module.WIKI_BOOTSTRAP_PROOF_PACKET = tmp / "wiki-bootstrap-proof.json"
    module.ACTIONABLE_QUEUE_PACKET = tmp / "actionable-improvement-queue.json"
    module.NO_ORPHAN_VALIDATOR_PACKET = tmp / "no-orphan-validator.json"
    module.ACTION_EXECUTOR_PACKET = tmp / "main-session-action-executor.json"
    module.ESCALATION_CONSUMER_PACKET = tmp / "main-session-escalation-consumer.json"
    module.PM_AUTONOMY_DISPATCHER_PACKET = tmp / "pm-autonomy-dispatcher.json"
    module.PM_JOB_WORKER_PACKET = tmp / "pm-job-worker-runner.json"
    module.PM_AUTONOMY_VERIFIER_PACKET = tmp / "pm-autonomy-verifier.json"
    module.PM_MAIN_ACTION_INBOX_PACKET = tmp / "pm-main-session-action-inbox.json"
    module.IMPLEMENTATION_COMPLETION_LEDGER = state / "implementation-completion-ledger.jsonl"
    module.CRON_MIGRATION_REPAIR_PLAN_PACKET = tmp / "cron-migration-repair-plan.json"
    module.TTS_SMOKE_FILE = tmp / "tts-hello-from-veritas.mp3"


def write_fixture_packets(module) -> None:
    write_json(module.STARTUP_PACKET, {
        "status": "ok",
        "generated_at_utc": "2026-06-20T06:00:00Z",
        "execution_efficiency_policy": module.implementation_router.execution_efficiency_policy(),
        "summary": {
            "wf84_status": "ready",
            "wf85_status": "ready",
            "pm_readiness_band": "yellow",
            "pm_ready_job_count": 1,
            "pm_blocked_job_count": 4,
            "cron_escalation_signal_count": 0,
            "cron_blocked_count": 0,
            "token_usage_total_tokens": 100,
            "token_usage_pricing_status": "loaded",
            "wiki_bootstrap_present": True,
            "wiki_bootstrap_schema": "veritas.wiki_bootstrap_proof.v2",
            "wiki_bootstrap_status": "bootstrap_ready_no_apply_authority",
            "wiki_bootstrap_validation": "ok",
            "wiki_bootstrap_gate": "material_bootstrap_ready",
            "wiki_bootstrap_required_file_count": 5,
            "wiki_bootstrap_validated_file_count": 5,
            "wiki_bootstrap_missing_file_count": 0,
            "wiki_bootstrap_missing_marker_count": 0,
            "wiki_bootstrap_missing_semantic_marker_count": 0,
            "wiki_bootstrap_semantic_render_hash_match": True,
            "wiki_bootstrap_recommendation_leak_guard_pass": True,
            "wiki_bootstrap_auto_apply_count": 0,
            "wiki_bootstrap_no_orphan_validation": "ok",
            "wiki_bootstrap_actionable_orphan_count": 0,
            "wiki_bootstrap_actionable_missing_contract_count": 0,
            "wiki_bootstrap_next_safe_action": "Open the WF88 wiki entry points before material work.",
        },
    })
    write_json(module.FUTURE_PACKET, {
        "status": "ok",
        "execution_efficiency_policy": module.implementation_router.execution_efficiency_policy(),
        "coding_outcome_efficiency": {
            "present": True,
            "route_conformant_count": 4,
            "route_mismatch_count": 0,
            "comparable_cohort_count": 1,
            "eligible_cohort_count": 0,
            "automatic_ranking_or_promotion_active": False,
        },
        "workflow_capsules": [
            {"workflow_id": "WF84", "effective_status": "ready"},
            {"workflow_id": "WF85", "effective_status": "ready"},
        ],
    })
    write_json(module.PM_PACKET, {
        "status": "ok",
        "summary": {
            "pm_readiness": {"readiness_band": "yellow", "average_score": 69.4},
            "implementation_queue": {
                "ready_job_count": 1,
                "blocked_job_count": 4,
                "top_job_id": "pm-finance-engine-refresh-artifact",
                "top_job_title": "Refresh unified finance route proof without capital authority",
                "top_ready_job_id": "pm-finance-engine-refresh-artifact",
                "top_ready_job_title": "Refresh unified finance route proof without capital authority",
            },
            "pm_cockpit_source_health": {"stale_required_count": 13},
            "stale_lane_digest": {
                "lanes": [{
                    "top_job_id": "pm-ticker-card-refresh-refresh-artifact",
                    "top_job_title": "Keep WF78 auto-router primary",
                    "next_action": "Run the tier promotion review refresh.",
                }]
            },
            "top_next_action": {
                "lane_id": "wf78_scaleout",
                "lane_status": "blocked",
                "description": "Needs tier promotion first.",
            },
            "finance_domain_repair_digest": {
                "pm_blocker_scope": "finance_domain_only",
                "total_repair_conveyor_row_count": 200,
                "implementation_blocker_count": 0,
                "tier_a_b_complete_and_current_band_count": 48,
                "tier_a_b_missing_decision_grade_band_count": 0,
                "tier_a_b_missing_decision_grade_band_tickers": [],
            },
            "sql_canon_health": {
                "status": "ok",
                "production_answer_count": 0,
                "counts": {"securities": 200},
                "checks": [{"name": "authority_false_flags_clean", "detail": {"tier_routing_state": 0}}],
            },
        },
    })
    write_json(module.CRON_PACKET, {"status": "ok", "summary": {"escalation_signal_count": 0, "blocked_count": 0}})
    write_json(module.TOKEN_USAGE_PACKET, {"status": "ok", "summary": {"total_tokens": 100, "pricing_status": "loaded"}})
    write_json(module.TOKEN_BUDGET_PACKET, {
        "status": "ok",
        "summary": {"total_tokens": 100, "pricing_status": "loaded", "last_24h_burn_status": "not_available_from_current_summary_packet"},
        "tokens_envelope": {
            "workspace_total_tokens": 100,
            "pricing_status": "loaded",
            "session_tokens_status": "unavailable_to_workspace_script",
            "last_24h_burn_status": "not_available_from_current_summary_packet",
        },
        "top_token_heavy_cron_jobs": [],
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    write_json(module.TMP_ARTIFACT_SPIRE_PACKET, {
        "status": "ok",
        "summary": {
            "tmp_json_count": 10,
            "tmp_total_mb": 2.5,
            "stale_json_count": 0,
            "wf78_json_count": 2,
            "cleanup_preview_eligible_count": 0,
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    module.ARTIFACT_INDEX_DB.parent.mkdir(parents=True, exist_ok=True)
    module.ARTIFACT_INDEX_DB.write_text("sqlite-placeholder", encoding="utf-8")
    write_json(module.SECURITY_WARNING_LEDGER_PACKET, {
        "status": "ok",
        "summary": {"warning_count": 0, "open_warning_count": 0, "owner_decision_required_count": 0},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    write_json(module.CRON_FRESHNESS_SPINE_PACKET, {
        "status": "ok",
        "summary": {
            "job_count": 3,
            "fresh_count": 2,
            "stale_count": 0,
            "requires_attention_count": 0,
            "urgent_attention_count": 0,
            "monitor_only_or_stale_count": 0,
            "quiet_success_count": 1,
            "blocked_count": 0,
        },
        "jobs": [],
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    write_json(module.WF78_PROMOTION_VISIBILITY_PACKET, {
        "status": "ok",
        "summary": {
            "candidate_count": 4,
            "owner_review_ready_count": 0,
            "market_refresh_pending_count": 1,
            "actionable_now_count": 1,
            "actionable_top10_count": 1,
            "production_visible_count": 1,
            "c_to_b_actionable_count": 1,
            "tier_c_attention_count": 1,
            "evidence_repair_count": 1,
        },
        "lanes": {"c_to_b_actionable": {"actionable_count": 1}},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    write_json(module.WF67_MANAGER_PACKET, {
        "status": "ok",
        "consumer_posture": "review_only_owner_gated_paper_manager",
        "summary": {"position_count": 1, "ready_tickers": ["NVDA"], "blocked_tickers": []},
    })
    write_json(module.WF67_PAPER_GUARD_PACKET, {
        "status": "ok",
        "ready_for_paper_submit_cancel": False,
        "findings": [{"code": "kill_switch_missing_or_expired", "severity": "critical", "value": "expired"}],
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    write_json(module.SHADOW_ELIGIBILITY_PACKET, {
        "status": "ok",
        "summary": {
            "would_buy_shadow_tickers": ["NVDA"],
            "execution_ready_count": 0,
            "next_safe_action": "Log shadow decisions only.",
        },
        "wf67_snapshot": {"guard_status": "blocked"},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    write_json(module.OWNER_GATED_PACKET, {
        "status": "ok",
        "summary": {
            "top_title": "NVDA approved for review advance; buy/order still blocked",
            "top_gate": "capital_deployment",
            "top_plain_status": "review advance approved; buy/order not approved",
            "next_safe_action": "Refresh NVDA first, then prepare an exact card only if still in band.",
        },
    })
    write_json(module.IMPROVEMENT_PACKET, {
        "status": "ok",
        "summary": {
            "top_improvement_title": "Route blocked cron signals",
            "top_improvement_sla_status": "overdue",
            "top_improvement_next_action": "Build dry-run cron migration plan.",
        },
    })
    write_json(module.WF88_WIKI_SYNTHESIS_PACKET, {
        "status": "wiki_synthesis_ready_no_apply_authority",
        "summary": {
            "wiki_page_count": 8,
            "self_prompt_count": 6,
            "followup_required_open_count": 1,
            "recommendation_later_outcome_graded_rows": 1,
        },
        "action_items": [{"id": "route-open-improvement-followups"}],
        "recommendation_leak_guard": {
            "pass": True,
            "open_unrouted_recommendation_count": 0,
            "auto_apply_count": 0,
        },
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
        "status": "actionable_queue_warning_no_apply_authority",
        "summary": {
            "action_item_count": 2,
            "orphan_count": 0,
            "missing_contract_count": 0,
            "owner_decision_count": 1,
            "hard_stop_count": 0,
            "monitor_only_count": 1,
            "top_action_title": "Route blocked cron signals",
            "top_action_class": "active_successor_followup",
            "top_action_destination": "wf88_followup_debt_triage",
            "top_next_action": "Resolve cron escalation.",
        },
        "validation": {"status": "warning", "errors": [], "warnings": ["monitor_review_visible:1"]},
    })
    write_json(module.NO_ORPHAN_VALIDATOR_PACKET, {
        "status": "no_orphan_validation_warning",
        "summary": {
            "validation_passed": True,
            "orphan_count": 0,
            "missing_contract_count": 0,
            "owner_decision_count": 1,
            "monitor_only_count": 1,
        },
        "validation": {"status": "warning", "errors": [], "warnings": ["monitor_rows_visible:1"]},
    })
    write_json(module.OTEL_LEARNING_PACKET, {
        "status": "ok",
        "generated_at_utc": "2026-06-20T06:00:00Z",
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
        "carry_forward_contract": {"status": "ready", "next_safe_action": "Keep OTEL carry-forward in startup/status/evening alert."},
        "auto_implementation_router": {"status": "gated_auto_route_no_auto_apply"},
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    write_json(module.ACTION_EXECUTOR_PACKET, {
        "status": "warning",
        "summary": {
            "parallel_helper_workstream": "pm-tier-promotion-review-refresh-artifact",
            "classification": "main_handoff",
            "executed": False,
            "next_safe_action": "Prepare proof lane.",
        },
    })
    write_json(module.ESCALATION_CONSUMER_PACKET, {"status": "ok", "summary": {}})
    write_json(module.TMP / "pm-implementation-job-queue.json", {
        "status": "ok",
        "summary": {
            "ready_job_count": 1,
            "blocked_job_count": 4,
            "top_ready_job_id": "pm-finance-engine-refresh-artifact",
            "top_ready_job_title": "Refresh unified finance route proof without capital authority",
        },
    })
    write_json(module.wf74_opportunity_packet(), {
        "status": "ok",
        "summary": {
            "opportunity_count": 2,
            "high_priority_count": 1,
            "top_opportunity_title": module.WORKFLOW_BLOCKER_FOLLOWUP_TITLE,
        },
        "opportunities": [
            {"title": module.WORKFLOW_BLOCKER_FOLLOWUP_TITLE, "priority": 89},
            {"title": module.CRON_MIGRATION_REPAIR_TITLE, "category": "cron_migration", "priority": 78},
        ],
    })
    write_json(module.wf74_auto_patch_packet(), {
        "status": "ok",
        "summary": {
            "patch_plan_count": 1,
            "skill_workshop_request_count": 0,
            "owner_gated_plan_count": 1,
            "auto_apply_count": 0,
        },
    })
    write_json(module.wf74_decision_docket_packet(), {
        "status": "ok",
        "summary": {
            "row_count": 3,
            "active_action_count": 0,
            "fix_now_count": 0,
            "owner_decision_count": 0,
            "market_session_accrual_count": 1,
            "monitor_only_count": 2,
            "hard_stop_count": 0,
            "next_safe_action": "No active implementation action; continue scheduled proof and monitor-only followups.",
        },
        "validation": {"status": "ok", "errors": [], "warnings": []},
    })
    write_json(module.workflow_blocker_followups_packet(), {
        "status": "ok",
        "summary": {"followup_count": 1, "route_counts": {"workflow_maturity": 1}},
        "followups": [{"route": "workflow_maturity"}],
    })
    write_json(module.cron_migration_repair_plan_packet(), {"status": "ok"})
    write_json(module.PM_AUTONOMY_DISPATCHER_PACKET, {
        "status": "ok",
        "summary": {
            "selected_action_type": "run_proof_refresh",
            "selected_job_id": "pm-finance-engine-refresh-artifact",
            "next_action": "Run proof commands for pm-finance-engine-refresh-artifact.",
        },
    })
    write_json(module.PM_JOB_WORKER_PACKET, {
        "status": "ok",
        "summary": {
            "action_type": "run_proof_refresh",
            "selected_job_id": "pm-ticker-card-refresh-refresh-artifact",
            "executed": True,
        },
    })
    write_json(module.PM_AUTONOMY_VERIFIER_PACKET, {"status": "ok", "summary": {}})
    write_json(module.PM_MAIN_ACTION_INBOX_PACKET, {
        "status": "ok",
        "action_type": "run_proof_refresh",
        "top_pending_job_id": "pm-finance-engine-refresh-artifact",
        "main_next_action": "Run proof commands for pm-finance-engine-refresh-artifact through pm_execution_loop, then verify and refresh status.",
    })


def test_status_card_builds_cached_rich_status_without_control_regeneration() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_temp_paths(module, root)
        write_fixture_packets(module)
        memory = module.MEMORY / f"{datetime.now(module.LOCAL_TZ).date().isoformat()}.md"
        memory.parent.mkdir(parents=True, exist_ok=True)
        memory.write_text(
            "## 2026-06-20 01:00 America/Phoenix - Startup Status Route Hardening\n"
            "- Status route became cached.\n"
            "## Post-Close SQL-First Cron Cleanup - 2026-06-20 02:00 UTC\n"
            "- Cron cleanup passed.\n",
            encoding="utf-8",
        )

        payload = module.build_payload(max_age_minutes=90)
        assert payload["schema"] == module.SCHEMA
        assert payload["validation"]["status"] == "ok"
        assert payload["authority_boundary"]["status_question_runs_control_producers"] is False
        assert payload["status_route_contract"]["default_command"] == r"python scripts\status_card_packet.py --read-only --frontdoor --render --validate"
        assert payload["status_route_contract"]["regenerates_pm_or_cron_packets"] is False
        assert payload["operating_posture"]["gateway"] == "openclaw-webchat-local"
        assert payload["operating_posture"]["model_route_match"] is None
        assert payload["operating_posture"]["actual_route"]["status"] == "unavailable_to_workspace_script"
        assert payload["operating_posture"]["actual_route"]["execution_backend"] is None
        assert payload["operating_posture"]["route_conformance"] == "unavailable"
        assert payload["operating_posture"]["tokens"]["session_tokens"] == "unavailable_to_workspace_script"
        assert "not cached by this card" not in json.dumps(payload["operating_posture"])
        assert payload["artifact_index_health"]["tmp_json_count"] == 10
        assert payload["cron_fleet_health"]["requires_attention_count"] == 0
        assert payload["wf78_visibility"]["canonical_top_of_funnel"] == "owner_review_ready_count"
        assert payload["paper_top_blocker_summary"]["top_blocker_code"] == "kill_switch_missing_or_expired"
        assert payload["security_warnings"]["open_warning_count"] == 0
        assert payload["finance_os"]["sql_canon"]["securities"] == 200
        assert payload["pm_queue"]["stale_cockpit_sources"] == 13
        assert payload["pm_queue"]["autonomy"]["inbox_top_job"] == "pm-finance-engine-refresh-artifact"
        assert payload["wf74_pickup"]["cron_blocked_or_escalated_count"] == 0
        assert payload["wf74_pickup"]["cron_migration_repair_visible"] is False
        assert payload["wf74_pickup"]["cron_migration_residue_visible"] is True
        assert payload["actionable_improvement_queue"]["orphan_count"] == 0
        assert payload["actionable_improvement_queue"]["no_orphan_validation_passed"] is True
        assert payload["wiki_bootstrap_proof"]["status"] == "bootstrap_ready_no_apply_authority"
        assert payload["wiki_bootstrap_proof"]["validation"] == "ok"
        assert payload["wiki_bootstrap_proof"]["validated_file_count"] == 5
        assert payload["execution_efficiency_policy"]["schema"] == "veritas.execution_efficiency_policy.v1"
        assert payload["execution_efficiency_policy"] == module.implementation_router.execution_efficiency_policy()
        assert payload["execution_efficiency_projection_source"] == "scripts/project_implementation_router.py"
        assert payload["future_efficiency_policy_matches_owner"] is True
        assert payload["startup_efficiency_policy_matches_owner"] is True
        assert payload["otel_learning_loop"]["status"] == "ok"
        assert payload["otel_learning_loop"]["carry_forward_status"] == "ready"
        assert payload["otel_learning_loop"]["auto_apply_allowed"] is False
        assert payload["active_items"][0]["item"] == "Refresh unified finance route proof without capital authority"
        assert all(item["item"] != "Keep WF78 auto-router primary" for item in payload["active_items"][:2])
        owner_items = [item for item in payload["active_items"] if item["source"] == "owner_gated"]
        assert owner_items[0]["state"] == "review advance approved; buy/order not approved"
        assert payload["recent_work"][-1] == "Post-Close SQL-First Cron Cleanup"

        text = module.render_markdown(payload)
        assert "### Finance OS" in text
        assert "### PM & Queue" in text
        assert "WF78 lanes" in text
        assert "OTEL carry-forward" in text
        assert "Wiki bootstrap proof" in text
        assert "Actionable improvements" in text
        assert "Paper blocker" in text
        assert "Capital deployment approved: `no`" in text
        assert "Read tmp/veritas-status-card-frontdoor.json" in text


def test_status_card_surfaces_sanitized_isolated_agent_fleet() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_temp_paths(module, root)
        write_fixture_packets(module)
        token_budget = json.loads(module.TOKEN_BUDGET_PACKET.read_text(encoding="utf-8"))
        token_budget["fleet_usage"] = {
            "present": True,
            "status": "partial",
            "generated_at_utc": "2026-08-09T18:00:00Z",
            "summary": {
                "configured_agent_count": 6,
                "utilized_agent_count": 4,
                "pricing_grade_attribution_coverage_percent": 75.0,
                "parent_job_completed_count": 3,
                "main_accepted_count": 2,
                "qa_yield_percent": 50.0,
                "rework_count": 1,
                "attribution_gap_count": 1,
            },
            "usage_windows": {
                "rolling_5h_observed": {"status": "partial_observed", "total_tokens": 100},
                "rolling_24h_gateway": {"status": "partial", "total_tokens": 200, "api_equivalent_is_not_invoice": True},
                "closed_7d_gateway": {"status": "partial", "total_tokens": 700, "api_equivalent_is_not_invoice": True},
            },
            "agents": [{
                "agent_id": "implementation-builder",
                "agent_role": "implementation_builder",
                "prompt": "must-not-leak",
                "utilization": {"reporting_total_tokens": 700, "utilization_share_percent": 50.0, "utilized": True},
                "outcomes": {"completed_lane_count": 2, "main_accepted_count": 1, "rework_count": 1, "attribution_gap_count": 1},
            }],
            "billing_semantics": {"api_equivalent_is_not_invoice": True, "actual_billed_cost_usd": None},
            "oauth_capacity_advisory": {"status": "current", "tier": "normal", "automatic_action_allowed": False},
        }
        write_json(module.TOKEN_BUDGET_PACKET, token_budget)

        payload = module.build_payload(max_age_minutes=90)
        fleet = payload["isolated_agent_fleet"]
        posture = payload["fleet_posture"]
        rendered = module.render_markdown(payload)
        serialized = json.dumps(fleet, sort_keys=True)

        assert payload["validation"]["status"] == "ok"
        assert fleet["status"] == "partial"
        assert fleet["summary"]["utilized_agent_count"] == 4
        assert fleet["summary"]["main_accepted_count"] == 2
        assert fleet["usage_windows"]["closed_7d_gateway"]["total_tokens"] == 700
        assert fleet["billing_semantics"]["api_equivalent_is_not_invoice"] is True
        assert fleet["oauth_capacity_advisory"]["automatic_action_allowed"] is False
        assert posture["schema"] == module.FLEET_POSTURE_SCHEMA
        assert posture["operating_model"]["configured_total_agent_count"] == 7
        assert posture["operating_model"]["main_authority"]["final_qc_owner"] is True
        assert posture["operating_model"]["main_authority"]["sole_acceptance_owner"] is True
        assert posture["containment"]["automatic_runtime_change_allowed"] is False
        assert "Agent fleet" in rendered
        assert "Fleet outcomes" in rendered
        assert "Fleet Posture" in rendered
        assert "must-not-leak" not in serialized
        assert '"prompt"' not in serialized


def test_read_only_renderer_uses_cached_card_without_writing() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_temp_paths(module, root)
        write_fixture_packets(module)
        payload = module.build_payload(max_age_minutes=90)
        write_json(module.OUT, payload)
        before = module.OUT.stat().st_mtime

        loaded, source = module.load_read_only_card()

        assert source == "status_card"
        assert loaded["validation"]["status"] == "ok"
        assert module.OUT.stat().st_mtime == before


def test_compact_frontdoor_defers_nested_proof_with_exact_hashes() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_temp_paths(module, root)
        write_fixture_packets(module)
        payload = module.build_payload(max_age_minutes=90)
        write_json(module.OUT, payload)

        frontdoor = module.compact_frontdoor_projection(payload, module.OUT)
        serialized = json.dumps(frontdoor, sort_keys=True)
        full_pointer = frontdoor["drilldown"]["artifacts"]["full_status"]

        assert frontdoor["schema"] == module.FRONTDOOR_SCHEMA
        assert full_pointer["present"] is True
        assert full_pointer["size_bytes"] == module.OUT.stat().st_size
        assert full_pointer["sha256"] == module.artifact_pointer(module.OUT)["sha256"]
        assert len(serialized.encode("utf-8")) < 20_000
        assert "input_artifacts" not in frontdoor
        assert "workflow_capsules" not in serialized
        assert frontdoor["efficiency_guard"]["minimum_comparable_main_accepted_jobs"] == 10
        assert frontdoor["efficiency_guard"]["automatic_route_promotion_allowed"] is False
        assert module.validation_for_loaded_frontdoor(frontdoor)["status"] == "ok"

        write_json(module.FRONTDOOR_OUT, frontdoor)
        before = module.FRONTDOOR_OUT.stat().st_mtime
        loaded, source = module.load_read_only_frontdoor()
        assert source == "status_frontdoor"
        assert loaded["validation"]["status"] == "ok"
        assert module.FRONTDOOR_OUT.stat().st_mtime == before
        assert "Nested proof is deferred" in module.render_markdown(loaded, source)


def test_compact_frontdoor_fails_closed_when_full_status_changes() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_temp_paths(module, root)
        write_fixture_packets(module)
        payload = module.build_payload(max_age_minutes=90)
        write_json(module.OUT, payload)
        write_json(module.FRONTDOOR_OUT, module.compact_frontdoor_projection(payload, module.OUT))
        payload["status"] = "changed-after-projection"
        write_json(module.OUT, payload)

        loaded, source = module.load_read_only_frontdoor()

        assert source == "status_frontdoor"
        assert loaded["status"] == "critical"
        assert "frontdoor_full_status_hash_mismatch" in loaded["validation"]["errors"]


def test_loaded_card_is_critical_when_completion_ledger_is_newer() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_temp_paths(module, root)
        write_fixture_packets(module)
        payload = module.build_payload(max_age_minutes=90)
        payload["generated_at_utc"] = "2026-06-20T01:00:00Z"
        write_json(module.OUT, payload)
        module.IMPLEMENTATION_COMPLETION_LEDGER.parent.mkdir(parents=True, exist_ok=True)
        module.IMPLEMENTATION_COMPLETION_LEDGER.write_text("{}\n", encoding="utf-8")

        validation = module.validation_for_loaded_card(payload)

        assert validation["status"] == "critical"
        assert "status_card_older_than.implementation_completion_ledger" in validation["errors"]


def test_loaded_card_is_critical_when_pm_autonomy_inbox_is_newer() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_temp_paths(module, root)
        write_fixture_packets(module)
        payload = module.build_payload(max_age_minutes=90)
        payload["generated_at_utc"] = "2026-06-20T01:00:00Z"
        write_json(module.OUT, payload)
        module.PM_MAIN_ACTION_INBOX_PACKET.write_text(
            json.dumps({"status": "ok", "action_type": "run_proof_refresh"}),
            encoding="utf-8",
        )

        validation = module.validation_for_loaded_card(payload)

        assert validation["status"] == "critical"
        assert "status_card_older_than.pm_main_session_action_inbox" in validation["errors"]


def test_loaded_card_is_critical_when_otel_learning_loop_is_newer() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_temp_paths(module, root)
        write_fixture_packets(module)
        payload = module.build_payload(max_age_minutes=90)
        payload["generated_at_utc"] = "2026-06-20T01:00:00Z"
        write_json(module.OUT, payload)
        module.OTEL_LEARNING_PACKET.write_text(
            json.dumps({"status": "ok", "validation": {"status": "ok"}}),
            encoding="utf-8",
        )

        validation = module.validation_for_loaded_card(payload)

        assert validation["status"] == "critical"
        assert "status_card_older_than.otel_learning_loop" in validation["errors"]


def test_stale_autonomy_handoff_does_not_win_active_items_when_job_not_ready() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_temp_paths(module, root)
        write_fixture_packets(module)
        pm = json.loads(module.PM_PACKET.read_text(encoding="utf-8"))
        queue = pm["summary"]["implementation_queue"]
        queue["ready_job_count"] = 0
        queue["top_ready_job_id"] = None
        queue["top_ready_job_title"] = None
        queue["top_job_id"] = "pm-wf78-scaleout-inspect-blocker"
        queue["top_job_title"] = "Advance 500-ticker feeder scaleout through the reputation gate"
        write_json(module.PM_PACKET, pm)

        payload = module.build_payload(max_age_minutes=90)

        assert payload["validation"]["status"] == "ok"
        assert payload["pm_queue"]["autonomy"]["current_handoff_valid"] is False
        assert "pm_autonomy_handoff.stale_or_not_ready" in payload["input_validation_warnings"]
        assert payload["active_items"][0]["item"] == "Advance 500-ticker feeder scaleout through the reputation gate"
        assert payload["active_items"][0]["state"] == "not_ready"


def test_wf74_monitor_only_residue_does_not_create_active_pickup() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_temp_paths(module, root)
        write_fixture_packets(module)
        pm = json.loads(module.PM_PACKET.read_text(encoding="utf-8"))
        queue = pm["summary"]["implementation_queue"]
        queue["ready_job_count"] = 0
        queue["active_job_count"] = 0
        queue["top_ready_job_id"] = None
        queue["top_ready_job_title"] = None
        queue["top_job_id"] = None
        queue["top_job_title"] = None
        write_json(module.PM_PACKET, pm)
        write_json(module.wf74_opportunity_packet(), {
            "status": "ok",
            "summary": {
                "opportunity_count": 5,
                "high_priority_count": 0,
                "top_opportunity_title": "Close remaining workflow-maturity follow-ups",
            },
            "opportunities": [
                {
                    "title": "Close remaining workflow-maturity follow-ups",
                    "category": "workflow_maturity",
                    "priority": 55,
                }
            ],
        })
        write_json(module.workflow_blocker_followups_packet(), {
            "status": "ok",
            "summary": {"followup_count": 4, "route_counts": {"workflow_maturity": 4}},
            "followups": [{"route": "workflow_maturity"}],
        })
        write_json(module.cron_migration_repair_plan_packet(), {"status": "monitor_only"})

        payload = module.build_payload(max_age_minutes=90)

        assert payload["wf74_pickup"]["actionable"] is False
        assert payload["wf74_pickup"]["decision_docket_active_action_count"] == 0
        assert payload["wf74_pickup"]["next_safe_action"]
        assert all(item["source"] != "wf74_pickup" for item in payload["active_items"])
        assert all(
            "main_session_greenkeeper_controller" not in str(action)
            for action in payload["next_actions"]
        )


def test_nested_input_validation_warning_changes_status_without_failing_contract() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_temp_paths(module, root)
        write_fixture_packets(module)
        write_json(module.CRON_PACKET, {
            "status": "error",
            "summary": {"escalation_signal_count": 0, "blocked_count": 0},
            "validation": {"status": "error", "errors": ["cron_probe_failed"]},
        })

        payload = module.build_payload(max_age_minutes=90)

        assert payload["status"] == "warning"
        assert payload["validation"]["status"] == "ok"
        assert "cron_control_packet.validation_error" in payload["input_validation_warnings"]


def test_read_only_falls_back_to_existing_startup_brief_when_card_missing() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_temp_paths(module, root)
        write_fixture_packets(module)

        loaded, source = module.load_read_only_card()

        assert source == "startup_brief_fallback"
        assert loaded["status"] == "fallback_startup_brief"
        assert loaded["validation"]["status"] == "ok"
        assert loaded["wiki_bootstrap_proof"]["validation"] == "ok"


def test_status_card_repairs_stale_policy_projections_without_mislabeling_source() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_temp_paths(module, root)
        write_fixture_packets(module)
        future = json.loads(module.FUTURE_PACKET.read_text(encoding="utf-8"))
        future["execution_efficiency_policy"]["route_order"] = []
        write_json(module.FUTURE_PACKET, future)
        startup = json.loads(module.STARTUP_PACKET.read_text(encoding="utf-8"))
        startup["execution_efficiency_policy"]["handoff_budget"] = {}
        write_json(module.STARTUP_PACKET, startup)

        payload = module.build_payload(max_age_minutes=90)
        assert payload["execution_efficiency_policy"] == module.implementation_router.execution_efficiency_policy()
        assert payload["execution_efficiency_projection_source"] == "scripts/project_implementation_router.py"
        assert payload["future_efficiency_policy_matches_owner"] is False
        assert payload["startup_efficiency_policy_matches_owner"] is False
        assert "future_session_packet.execution_efficiency_policy_owner_mismatch" in payload["input_validation_warnings"]
        assert "startup_brief_packet.execution_efficiency_policy_owner_mismatch" in payload["input_validation_warnings"]


def main() -> int:
    test_status_card_builds_cached_rich_status_without_control_regeneration()
    test_status_card_surfaces_sanitized_isolated_agent_fleet()
    test_read_only_renderer_uses_cached_card_without_writing()
    test_compact_frontdoor_defers_nested_proof_with_exact_hashes()
    test_compact_frontdoor_fails_closed_when_full_status_changes()
    test_loaded_card_is_critical_when_completion_ledger_is_newer()
    test_loaded_card_is_critical_when_pm_autonomy_inbox_is_newer()
    test_loaded_card_is_critical_when_otel_learning_loop_is_newer()
    test_stale_autonomy_handoff_does_not_win_active_items_when_job_not_ready()
    test_wf74_monitor_only_residue_does_not_create_active_pickup()
    test_nested_input_validation_warning_changes_status_without_failing_contract()
    test_read_only_falls_back_to_existing_startup_brief_when_card_missing()
    test_status_card_repairs_stale_policy_projections_without_mislabeling_source()
    print("status card packet tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
