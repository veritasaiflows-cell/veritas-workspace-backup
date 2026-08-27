from __future__ import annotations

import cron_changed_input_prefilter_plan as prefilter


def test_cron_changed_input_prefilter_plan_preserves_cron_boundaries() -> None:
    artifacts = {
        "token_efficiency": {
            "status": "warning",
            "summary": {
                "token_event_count": 10,
                "total_tokens": 1000,
                "top_candidate": "Finance - Ticker Card Freshness Owner Runner",
                "api_equivalent_cost_usd": 0.10,
                "api_equivalent_estimate_status": "partial_unknown_input_semantics_or_missing_rate",
                "api_equivalent_cost_rows": 1,
                "api_equivalent_cost_event_coverage_percent": 10.0,
                "estimated_chatgpt_credits": 1.25,
                "chatgpt_credit_estimate_status": "partial_separate_no_public_rate_or_missing_rate",
                "estimated_chatgpt_credit_rows": 1,
                "chatgpt_credit_event_coverage_percent": 10.0,
                "actual_billed_cost_usd": None,
            },
            "billing_semantics": {
                "billing_mode": "oauth_subscription",
                "api_equivalent_is_not_invoice": True,
            },
            "oauth_capacity_control": {
                "state": "normal",
                "remaining_percent": 62.0,
                "automatic_action_allowed": False,
            },
            "top_cron_efficiency_candidates": [
                {
                    "rank": 1,
                    "cron_job_name": "Finance - Ticker Card Freshness Owner Runner",
                    "run_count": 5,
                    "total_tokens": 1000,
                    "tokens_per_run": 200,
                    "api_equivalent_cost_usd": 0.10,
                    "api_equivalent_cost_rows": 1,
                    "api_equivalent_estimate_status": "partial_unknown_input_semantics_or_missing_rate",
                    "estimated_cost": 0.10,
                    "estimated_chatgpt_credits": 1.25,
                    "estimated_chatgpt_credit_rows": 1,
                    "chatgpt_credit_estimate_status": "partial_separate_no_public_rate_or_missing_rate",
                    "candidate_types": ["changed_only_prefilter_review"],
                    "predispatch_contract": {
                        "recommended": True,
                        "mode": "changed_input_hash_before_model_spawn",
                        "required_proof": ["input_signature hash"],
                        "acceptance": "unchanged skips, changed runs",
                        "stop_line": "No schedule/model mutation",
                    },
                }
            ],
        },
        "cron_predispatch_efficiency": {
            "status": "warning",
            "candidates": [
                {
                    "cron_name": "Finance - Ticker Card Freshness Owner Runner",
                    "payload_kind": "agentTurn",
                    "implementation_route": "cron_payload_diff_required",
                    "script_level_prefilter_saves_model_tokens": False,
                    "existing_changed_only_gate": False,
                }
            ],
        },
        "cron_control": {},
        "workspace_automation_approval": {},
    }

    packet = prefilter.build_packet(artifacts, limit=3)

    assert packet["schema"] == "veritas.cron_changed_input_prefilter_plan.v1"
    assert packet["validation"]["status"] == "ok"
    assert packet["status"] == "prefilter_patch_queue_ready"
    assert packet["summary"]["ready_for_scoped_patch_design_count"] == 1
    assert packet["summary"]["finance_noncapital_ready_count"] == 1
    assert packet["summary"]["pre_model_payload_diff_required_count"] == 1
    assert packet["summary"]["token_event_count"] == 10
    assert packet["summary"]["api_equivalent_cost_usd"] == 0.10
    assert packet["summary"]["api_equivalent_estimate_status"].startswith("partial_")
    assert packet["summary"]["api_equivalent_cost_rows"] == 1
    assert packet["summary"]["estimated_chatgpt_credits"] == 1.25
    assert packet["summary"]["chatgpt_credit_estimate_status"].startswith("partial_")
    assert packet["summary"]["actual_billed_cost_usd"] is None
    assert packet["summary"]["oauth_quota_state"] == "normal"
    assert packet["patch_queue"][0]["api_equivalent_cost_usd"] == 0.10
    assert packet["billing_semantics"]["api_equivalent_is_not_invoice"] is True
    assert packet["oauth_capacity_control"]["automatic_action_allowed"] is False
    assert packet["patch_queue"][0]["patch_scope"] == "finance_noncapital_review"
    assert packet["patch_queue"][0]["patch_stage"] == "pre_model_payload_diff_required"
    assert packet["patch_queue"][0]["script_level_prefilter_saves_model_tokens"] is False
    rendered = prefilter.render_md(packet)
    assert "1/10 events priced" in rendered

    boundary = packet["authority_boundary"]
    for flag in (
        "cron_schedule_mutation_allowed",
        "cron_model_route_mutation_allowed",
        "runtime_config_mutation_allowed",
        "raw_prompt_capture_allowed",
        "raw_response_capture_allowed",
        "tool_payload_capture_allowed",
        "finance_canon_or_portfolio_mutation_allowed",
        "paper_or_live_execution_allowed",
        "owner_approval_inferred",
    ):
        assert boundary[flag] is False, flag
