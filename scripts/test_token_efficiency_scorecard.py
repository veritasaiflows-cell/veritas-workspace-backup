from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "token_efficiency_scorecard.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("token_efficiency_scorecard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed(
    root: Path,
    module,
    *,
    implementation_gap_count: int = 3,
    failed_count: int = 1,
    quota_status: str = "current",
    quota_tier: str = "normal",
    include_capacity: bool = True,
    automatic_action_allowed: bool = False,
    api_equivalent_is_not_invoice: bool = True,
    actual_billed_cost_usd=None,
) -> tuple[Path, Path, Path]:
    module.ROOT = root
    module.TMP = root / "tmp"
    token_usage = module.TMP / "token-usage-ledger-current.json"
    token_budget = module.TMP / "token-budget-status.json"
    contract_dir = root / "state" / "cron-contracts"
    write_json(contract_dir / "future-session.json", {
        "name": "Runtime - Future Session Packet Refresh",
        "enabled": True,
    })
    token_usage_payload = {
        "status": "ok",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "token_event_count": 20,
            "total_tokens": 1_000_000,
            "api_equivalent_cost_usd": 2.5,
            "api_equivalent_estimate_status": "complete",
            "api_equivalent_cost_rows": 20,
            "api_equivalent_cost_event_coverage_percent": 100.0,
            "api_equivalent_priced_tokens": 1_000_000,
            "estimated_cost_total": 2.5,
            "estimated_chatgpt_credits": 25.0,
            "chatgpt_credit_estimate_status": "complete",
            "estimated_chatgpt_credit_rows": 20,
            "chatgpt_credit_event_coverage_percent": 100.0,
            "chatgpt_credit_priced_tokens": 1_000_000,
            "actual_billed_cost_usd": actual_billed_cost_usd,
            "cron_token_event_count": 20,
            "implementation_token_event_count": 0,
            "implementation_token_gap_count": implementation_gap_count,
        },
        "billing_semantics": {
            "billing_mode": "oauth_subscription",
            "api_equivalent_is_not_invoice": api_equivalent_is_not_invoice,
            "actual_billed_cost_is_inferred": False,
        },
        "top_cron_jobs_by_tokens": [
            {
                "cron_job_name": "Runtime - Future Session Packet Refresh",
                "count": 12,
                "total_tokens": 650_000,
                "input_tokens": 50_000,
                "cached_input_tokens": 595_000,
                "output_tokens": 5_000,
                "failed_or_error_count": 0,
                "api_equivalent_cost_usd": 0.65,
                "api_equivalent_cost_rows": 12,
                "api_equivalent_estimate_status": "complete",
                "estimated_cost": 0.65,
                "estimated_chatgpt_credits": 6.5,
                "estimated_chatgpt_credit_rows": 12,
                "chatgpt_credit_estimate_status": "complete",
            },
            {
                "cron_job_name": "Ops - OTEL Local Digest",
                "count": 9,
                "total_tokens": 300_000,
                "input_tokens": 120_000,
                "cached_input_tokens": 175_000,
                "output_tokens": 5_000,
                "failed_or_error_count": failed_count,
                "api_equivalent_cost_usd": 0.3,
                "api_equivalent_cost_rows": 9,
                "api_equivalent_estimate_status": "complete",
                "estimated_cost": 0.3,
                "estimated_chatgpt_credits": 3.0,
                "estimated_chatgpt_credit_rows": 9,
                "chatgpt_credit_estimate_status": "complete",
            },
        ],
        "validation": {"status": "ok"},
    }
    if include_capacity:
        token_usage_payload["oauth_capacity_control"] = {
            "status": quota_status,
            "tier": quota_tier,
            "remaining_percent": 42.0,
            "reset_at_utc": "2026-08-15T00:00:00Z",
            "days_until_reset": 6,
            "reserve_percent": 20.0,
            "daily_burn_guidance": "preserve reserve",
            "automatic_action_allowed": automatic_action_allowed,
        }
    write_json(token_usage, token_usage_payload)
    token_budget_payload = {
        "status": "warning" if implementation_gap_count else "ok",
        "generated_at_utc": module.utc_now(),
        "summary": {
            "api_equivalent_cost_usd": 2.5,
            "api_equivalent_estimate_status": "complete",
            "api_equivalent_cost_rows": 20,
            "api_equivalent_cost_event_coverage_percent": 100.0,
            "estimated_cost_total": 2.5,
            "estimated_chatgpt_credits": 25.0,
            "chatgpt_credit_estimate_status": "complete",
            "estimated_chatgpt_credit_rows": 20,
            "chatgpt_credit_event_coverage_percent": 100.0,
            "actual_billed_cost_usd": actual_billed_cost_usd,
        },
        "billing_semantics": token_usage_payload["billing_semantics"],
        "validation": {"status": "ok"},
    }
    if include_capacity:
        token_budget_payload["oauth_capacity_control"] = token_usage_payload["oauth_capacity_control"]
    write_json(token_budget, token_budget_payload)
    return token_usage, token_budget, contract_dir


def replace_capacity_control(token_usage: Path, token_budget: Path, control: dict) -> None:
    for path in (token_usage, token_budget):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["oauth_capacity_control"] = control
        write_json(path, payload)


def advisory_capacity_control(
    *,
    tier: str = "normal",
    snapshot_status: str = "fresh",
    snapshot_age_hours: float | None = 1.0,
    capacity_known: bool = True,
) -> dict:
    return {
        "state": tier,
        "status": "current",
        "tier": tier,
        "quota_tier": tier,
        "snapshot_status": snapshot_status,
        "snapshot_age_hours": snapshot_age_hours,
        "capacity_known": capacity_known,
        "remaining_percent": 42.0,
        "reserve_percent": 20.0,
        "automatic_action_allowed": False,
        "policy": {
            "event_refresh": {
                "high_burn_preflight_max_snapshot_age_hours": 3.5,
            },
        },
    }


def test_scorecard_surfaces_api_reduction_and_gap_actions() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, token_budget, contract_dir = seed(Path(tmpdir), module)
        payload = module.build_payload(token_usage, token_budget, contract_dir)

        assert payload["status"] == "warning"
        assert payload["validation"]["status"] == "warning"
        assert payload["summary"]["api_call_reduction_candidate_count"] >= 1
        assert payload["summary"]["predispatch_skip_candidate_count"] >= 1
        assert payload["summary"]["implementation_token_gap_count"] == 3
        assert payload["authority_boundary"]["cron_schedule_mutation_allowed"] is False
        assert payload["authority_boundary"]["platform_billing_api_call_allowed"] is False
        assert payload["authority_boundary"]["automatic_quota_action_allowed"] is False
        assert any(row["id"] == "close-implementation-token-attribution-gap" for row in payload["action_items"])
        assert payload["top_cron_efficiency_candidates"][0]["cron_job_name"] == "Runtime - Future Session Packet Refresh"
        assert payload["summary"]["selected_next_candidate"] == "Runtime - Future Session Packet Refresh"
        assert payload["summary"]["selected_next_candidate_type"] == "changed_only_prefilter"
        assert payload["selected_next_candidate"]["stop_line"].startswith("No cron schedule")
        assert payload["top_cron_efficiency_candidates"][0]["predispatch_contract"]["mode"] == "changed_input_hash_before_model_spawn"
        assert payload["cron_predispatch_recommendations"][0]["cron_job_name"] == "Runtime - Future Session Packet Refresh"
        assert payload["summary"]["active_ledger_job_count"] == 1
        assert payload["summary"]["historical_or_unverified_ledger_job_count"] == 1
        assert payload["historical_or_unverified_cron_spend"][0]["cron_job_name"] == "Ops - OTEL Local Digest"
        assert payload["top_cron_efficiency_candidates"][0]["api_equivalent_cost_usd"] == 0.65
        assert payload["top_cron_efficiency_candidates"][0]["estimated_cost"] == 0.65


def test_scorecard_reads_action_required_attribution_denominator_from_bridge() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        token_usage, token_budget, contract_dir = seed(Path(tmpdir), module)
        bridge = root / "tmp" / "implementation-token-attribution-bridge.json"

        def bridge_payload(action_required: int) -> dict:
            return {
                "status": "warning" if action_required else "ok",
                "generated_at_utc": module.utc_now(),
                "summary": {
                    "gap_resolution_status": "stamp_required" if action_required else "terminal_unavailable_only",
                    "implementation_token_gap_count": 597,
                    "action_required_supported_runtime_gap_count": action_required,
                },
                "validation": {"status": "ok"},
            }

        write_json(bridge, bridge_payload(0))
        classified = module.build_payload(token_usage, token_budget, contract_dir, attribution_bridge_path=bridge)
        assert classified["summary"]["attribution_gap_action_required_count"] == 0
        assert classified["summary"]["attribution_gap_resolution_status"] == "terminal_unavailable_only"
        assert classified["summary"]["bridge_needed"] is False
        assert all(row["id"] != "close-implementation-token-attribution-gap" for row in classified["action_items"])
        assert all(not warning.startswith("implementation_token_gap_count") for warning in classified["validation"]["warnings"])

        write_json(bridge, bridge_payload(2))
        actionable = module.build_payload(token_usage, token_budget, contract_dir, attribution_bridge_path=bridge)
        assert actionable["summary"]["bridge_needed"] is True
        assert "attribution_gap_action_required_count:2" in actionable["validation"]["warnings"]
        assert any(row["id"] == "close-implementation-token-attribution-gap" for row in actionable["action_items"])


def test_scorecard_can_be_clean_when_no_gaps_or_failures() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, token_budget, contract_dir = seed(Path(tmpdir), module, implementation_gap_count=0, failed_count=0)
        payload = module.build_payload(token_usage, token_budget, contract_dir)

        assert payload["summary"]["implementation_token_gap_count"] == 0
        assert payload["validation"]["status"] == "ok"
        assert payload["status"] == "ok"
        assert payload["summary"]["api_call_reduction_candidate_count"] >= 1
        assert payload["selected_next_candidate"]["candidate_type"] == "changed_only_prefilter"


def test_scorecard_propagates_oauth_fields_aliases_and_markdown_labels() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, token_budget, contract_dir = seed(
            Path(tmpdir),
            module,
            implementation_gap_count=0,
            failed_count=0,
            quota_tier="reduce_routine",
        )
        payload = module.build_payload(token_usage, token_budget, contract_dir)
        quota_action = next(row for row in payload["action_items"] if row["id"] == "oauth-quota-capacity-guidance")
        markdown = module.render_md(payload)

        assert payload["validation"]["status"] == "ok"
        assert payload["billing_semantics"]["billing_mode"] == "oauth_subscription"
        assert payload["billing_semantics"]["api_equivalent_is_not_invoice"] is True
        assert payload["summary"]["api_equivalent_cost_usd"] == 2.5
        assert payload["summary"]["estimated_cost_total"] == 2.5
        assert payload["summary"]["estimated_cost_total_deprecated_alias_for"] == "api_equivalent_cost_usd"
        assert payload["summary"]["estimated_chatgpt_credits"] == 25.0
        assert payload["summary"]["actual_billed_cost_usd"] is None
        assert payload["summary"]["oauth_quota_tier"] == "reduce_routine"
        assert payload["summary"]["oauth_remaining_percent"] == 42.0
        assert quota_action["automatic_action_allowed"] is False
        assert "Terra/Luna" in quota_action["next_action"]
        assert "Sol only for high-value integration" in quota_action["next_action"]
        assert "API-equivalent benchmark" in markdown
        assert "Actual billed cost" in markdown
        assert "Estimated ChatGPT credits" in markdown
        assert "OAuth quota tier" in markdown


def test_quota_tier_actions_are_advisory_and_complete() -> None:
    module = load_module()
    expected_text = {
        "normal": "Preserve the OAuth reserve and current routing policy.",
        "reduce_routine": "Recommend Terra/Luna for routine work and Sol only for high-value integration.",
        "pause_noncritical": "Recommend review or pause of noncritical model-driven work, with no schedule change.",
        "urgent_only": "Recommend urgent or high-value model-driven work only.",
    }
    for tier, expected in expected_text.items():
        action = module.quota_action_item({
            "status": "current",
            "tier": tier,
            "automatic_action_allowed": False,
        })
        assert action["next_action"] == expected
        assert action["automatic_action_allowed"] is False
        assert "no automatic throttling" in action["stop_line"]

    for status in ("stale", "unavailable"):
        action = module.quota_action_item({
            "status": status,
            "tier": "normal",
            "automatic_action_allowed": False,
        })
        assert action["state"] == "refresh_required"
        assert action["next_action"] == "Refresh the OAuth quota snapshot; do not throttle automatically."


def test_scorecard_missing_or_stale_quota_warns_without_blocking() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, token_budget, contract_dir = seed(
            Path(tmpdir), module, implementation_gap_count=0, failed_count=0, include_capacity=False
        )
        payload = module.build_payload(token_usage, token_budget, contract_dir)
        quota_action = next(row for row in payload["action_items"] if row["id"] == "oauth-quota-capacity-guidance")

        assert payload["status"] == "warning"
        assert payload["validation"]["status"] == "warning"
        assert payload["validation"]["errors"] == []
        assert "oauth_capacity_snapshot_missing_or_stale" in payload["validation"]["warnings"]
        assert quota_action["state"] == "refresh_required"
        assert quota_action["automatic_action_allowed"] is False


def test_high_burn_oauth_capacity_preflight_states_are_advisory_only() -> None:
    module = load_module()
    candidate = module.classify_job({
        "cron_job_name": "High Burn Fixture",
        "count": 12,
        "total_tokens": 650_000,
        "input_tokens": 50_000,
        "cached_input_tokens": 595_000,
        "output_tokens": 5_000,
    }, 1)
    before = json.dumps(candidate, sort_keys=True)
    cases = [
        (advisory_capacity_control(), "advisory_current"),
        (advisory_capacity_control(tier="reduce_routine"), "review_required"),
        (advisory_capacity_control(snapshot_age_hours=4.0), "refresh_required"),
        (advisory_capacity_control(snapshot_status="invalid"), "refresh_required"),
        ({}, "refresh_required"),
    ]
    for control, expected_state in cases:
        preflight = module.oauth_capacity_preflight_for_candidate(candidate, control)
        assert preflight["required"] is True
        assert preflight["state"] == expected_state
        assert preflight["advisory_only"] is True
        assert preflight["automatic_action_allowed"] is False
        assert preflight["automatic_dispatch_allowed"] is False
        assert preflight["state"] not in {"allowed", "blocked"}
    assert json.dumps(candidate, sort_keys=True) == before


def test_scorecard_attaches_safe_preflight_only_to_repeated_high_burn_candidates() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, token_budget, contract_dir = seed(
            Path(tmpdir), module, implementation_gap_count=0, failed_count=0
        )
        control = advisory_capacity_control()
        control["raw_status_text"] = "private-capacity-page-text"
        control["account_identity"] = "private-account-identity"
        replace_capacity_control(token_usage, token_budget, control)
        payload = module.build_payload(token_usage, token_budget, contract_dir)
        high_burn = payload["top_cron_efficiency_candidates"][0]
        historical = payload["historical_or_unverified_cron_spend"][0]
        preflight = high_burn["oauth_capacity_preflight"]

        assert "repeated_high_burn_job" in high_burn["reasons"]
        assert preflight["required"] is True
        assert preflight["state"] == "advisory_current"
        assert preflight["max_snapshot_age_hours"] == 3.5
        assert preflight["automatic_action_allowed"] is False
        assert preflight["automatic_dispatch_allowed"] is False
        assert "private-capacity-page-text" not in json.dumps(preflight, sort_keys=True)
        assert "private-account-identity" not in json.dumps(preflight, sort_keys=True)
        assert historical["oauth_capacity_preflight"]["required"] is False
        assert historical["oauth_capacity_preflight"]["state"] == "not_applicable"
        assert historical["oauth_capacity_preflight"]["automatic_dispatch_allowed"] is False
        assert high_burn["predispatch_contract"]["mode"] == "changed_input_hash_before_model_spawn"
        assert payload["selected_next_candidate"]["cron_job_name"] == "Runtime - Future Session Packet Refresh"


def test_stale_or_missing_high_burn_preflight_never_blocks_or_dispatches() -> None:
    module = load_module()
    for control in (advisory_capacity_control(snapshot_age_hours=4.0), {}):
        with tempfile.TemporaryDirectory() as tmpdir:
            token_usage, token_budget, contract_dir = seed(
                Path(tmpdir), module, implementation_gap_count=0, failed_count=0
            )
            replace_capacity_control(token_usage, token_budget, control)
            payload = module.build_payload(token_usage, token_budget, contract_dir)
            high_burn = payload["top_cron_efficiency_candidates"][0]
            preflight = high_burn["oauth_capacity_preflight"]

            assert preflight["state"] == "refresh_required"
            assert preflight["automatic_action_allowed"] is False
            assert preflight["automatic_dispatch_allowed"] is False
            assert payload["validation"]["errors"] == []
            assert high_burn["predispatch_contract"]["mode"] == "changed_input_hash_before_model_spawn"
            assert payload["selected_next_candidate"]["cron_job_name"] == "Runtime - Future Session Packet Refresh"


def test_scorecard_blocks_bill_conflation_and_automatic_quota_action() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, token_budget, contract_dir = seed(
            Path(tmpdir),
            module,
            implementation_gap_count=0,
            failed_count=0,
            automatic_action_allowed=True,
            api_equivalent_is_not_invoice=False,
            actual_billed_cost_usd=2.5,
        )
        payload = module.build_payload(token_usage, token_budget, contract_dir)

        assert payload["status"] == "blocked"
        assert payload["authority_boundary"]["cron_schedule_mutation_allowed"] is False
        assert "no Platform billing API call or inferred invoice" in payload["blocked_actions"]
        assert "oauth_api_equivalent_presented_as_actual_bill" in payload["validation"]["errors"]
        assert "oauth_actual_billed_cost_lacks_owner_entered_provenance" in payload["validation"]["errors"]
        assert "oauth_capacity_automatic_action_enabled" in payload["validation"]["errors"]


def test_scorecard_normalizes_core_capacity_field_names() -> None:
    module = load_module()
    normalized = module.normalize_oauth_capacity_control({
        "state": "normal",
        "quota_tier": "normal",
        "snapshot_status": "fresh",
        "capacity_known": True,
        "remaining_percent": 62.0,
        "days_to_reset": 6.25,
        "max_daily_percentage_point_burn_preserving_reserve": 6.72,
        "policy": {"thresholds_percent": {"reserve": 20}},
        "automatic_action_allowed": False,
    })
    assert normalized["status"] == "current"
    assert normalized["tier"] == "normal"
    assert normalized["days_until_reset"] == 6.25
    assert normalized["reserve_percent"] == 20
    assert normalized["daily_burn_guidance"] == 6.72


def test_partial_pricing_coverage_never_becomes_a_fake_per_run_average() -> None:
    module = load_module()
    row = module.classify_job({
        "cron_job_name": "Partial Coverage",
        "count": 10,
        "total_tokens": 1_000,
        "input_tokens": 100,
        "cached_input_tokens": 0,
        "output_tokens": 10,
        "api_equivalent_cost_usd": 1.0,
        "api_equivalent_cost_rows": 1,
        "api_equivalent_estimate_status": "partial_unknown_input_semantics_or_missing_rate",
        "estimated_chatgpt_credits": 10.0,
        "estimated_chatgpt_credit_rows": 1,
        "chatgpt_credit_estimate_status": "partial_separate_no_public_rate_or_missing_rate",
    }, 1)
    assert row["api_equivalent_cost_per_run_usd"] is None
    assert row["api_equivalent_cost_per_priced_run_usd"] == 1.0
    assert row["estimated_chatgpt_credits_per_run"] is None
    assert row["estimated_chatgpt_credits_per_priced_run"] == 10.0


def test_scorecard_integrates_fleet_outcomes_without_leaking_content() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, token_budget, contract_dir = seed(
            Path(tmpdir), module, implementation_gap_count=0, failed_count=0
        )
        budget_payload = json.loads(token_budget.read_text(encoding="utf-8"))
        budget_payload["fleet_usage"] = {
            "present": True,
            "status": "partial",
            "outcome_telemetry_status": "verified",
            "generated_at_utc": "2026-08-09T18:00:00Z",
            "usage_windows": {
                "rolling_5h_observed": {"status": "partial_observed", "total_tokens": 100},
                "rolling_24h_gateway": {"status": "partial", "total_tokens": 200, "api_equivalent_is_not_invoice": True},
                "closed_7d_gateway": {"status": "partial", "total_tokens": 700, "api_equivalent_is_not_invoice": True},
            },
            "summary": {
                "configured_agent_count": 6,
                "utilized_agent_count": 4,
                "pricing_grade_attribution_coverage_percent": 75.0,
                "parent_job_count": 4,
                "parent_job_completed_count": 3,
                "completed_lane_count": 4,
                "outcome_eligible_completed_lane_count": 4,
                "main_accepted_count": 3,
                "main_acceptance_pending_count": 1,
                "qa_pass_count": 2,
                "qa_yield_percent": 50.0,
                "rework_count": 1,
                "attribution_gap_count": 1,
            },
            "agents": [{
                "agent_id": "implementation-builder",
                "agent_role": "implementation_builder",
                "secret_prompt": "must-not-leak",
                "utilization": {
                    "reporting_source": "gateway_usage_cost",
                    "reporting_total_tokens": 700,
                    "utilization_share_percent": 50.0,
                    "utilized": True,
                },
                "outcomes": {
                    "completed_lane_count": 2,
                    "outcome_eligible_completed_lane_count": 2,
                    "main_accepted_count": 1,
                    "qa_pass_count": 1,
                    "rework_count": 1,
                    "attribution_gap_count": 1,
                },
            }],
            "billing_semantics": {"api_equivalent_is_not_invoice": True, "actual_billed_cost_usd": None},
            "oauth_capacity_advisory": {"status": "current", "tier": "normal", "automatic_action_allowed": False},
        }
        write_json(token_budget, budget_payload)
        source_payload = json.loads(token_usage.read_text(encoding="utf-8"))
        source_payload.update({
            "schema": "veritas.token_usage_ledger_current.v1",
            "status": "ok",
            "validation": {"status": "ok", "errors": [], "warnings": []},
            "isolated_agent_event_validation": {"status": "ok", "finding_count": 0, "findings": []},
            "per_agent_usage": [{
                "agent_id": "implementation-builder",
                "reporting_source": "gateway_usage_cost",
                "reporting_total_tokens": 700,
                "utilized": True,
                "utilization_share_percent": 50.0,
                "session_event_count": 4,
                "session_attribution_grade_event_count": 3,
                "session_pricing_grade_event_count": 3,
            }],
            "fleet_reporting": {
                "schema": "veritas.isolated_agent_fleet_reporting.v1",
                "outcome_credit_contract": {
                    "version": "veritas.fleet_outcome_credit.v1",
                    "status": "verified",
                    "post_cutover_source_reverification_required": True,
                },
                "summary": {
                    "gateway_closed_7d_ready_agent_count": 1,
                    "gateway_24h_ready_agent_count": 1,
                },
                "agents": [{
                    "agent_id": "implementation-builder",
                    "agent_role": "implementation_builder",
                    "usage_windows": {},
                    "outcomes": {
                        "lane_count": 4,
                        "completed_lane_count": 4,
                        "outcome_creditable_completed_lane_count": 3,
                        "outcome_uncreditable_completed_lane_count": 1,
                        "outcome_tracking_start_utc": "2026-08-09T18:00:00Z",
                        "outcome_eligible_completed_lane_count": 4,
                        "historical_or_untracked_completed_lane_count": 0,
                        "parent_job_count": 4,
                        "parent_job_completed_count": 3,
                        "main_accepted_count": 3,
                        "main_acceptance_pending_count": 1,
                        "qa_review_completed_count": 4,
                        "qa_pass_count": 2,
                        "qa_yield_percent": 50.0,
                        "rework_count": 1,
                        "attribution_gap_count": 1,
                    },
                }],
            },
        })
        source_payload["summary"].update({
            "configured_isolated_agent_count": 6,
            "observed_isolated_agent_count": 4,
            "utilized_isolated_agent_count": 4,
            "isolated_agent_session_event_count": 4,
            "isolated_agent_attribution_grade_event_count": 3,
            "isolated_agent_pricing_grade_event_count": 3,
        })
        write_json(token_usage, source_payload)

        payload = module.build_payload(token_usage, token_budget, contract_dir)
        fleet = payload["fleet_efficiency"]
        serialized = json.dumps(fleet, sort_keys=True)

        assert payload["status"] == "warning"
        assert payload["summary"]["fleet_utilized_agent_count"] == 4
        assert payload["summary"]["fleet_pricing_grade_attribution_coverage_percent"] == 75.0
        assert payload["summary"]["fleet_parent_job_completed_count"] == 3
        assert payload["summary"]["fleet_main_accepted_count"] == 3
        assert payload["summary"]["fleet_qa_yield_percent"] == 50.0
        assert payload["summary"]["fleet_rework_count"] == 1
        assert payload["summary"]["fleet_attribution_gap_count"] == 1
        assert any(row["id"] == "repair-isolated-agent-attribution-gaps" for row in payload["action_items"])
        assert any(row["id"] == "review-isolated-agent-rework" for row in payload["action_items"])
        assert fleet["interpretation"]["token_usage_is_model_quality_proof"] is False
        assert fleet["billing_semantics"]["api_equivalent_is_not_invoice"] is True
        assert "must-not-leak" not in serialized
        assert "secret_prompt" not in serialized


def test_scorecard_never_uses_legacy_fleet_completion_fields_as_outcome_credit() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, token_budget, contract_dir = seed(
            Path(tmpdir), module, implementation_gap_count=0, failed_count=0
        )
        budget_payload = json.loads(token_budget.read_text(encoding="utf-8"))
        budget_payload["fleet_usage"] = {
            "present": True,
            "status": "partial",
            "summary": {
                "completed_lane_count": 1,
                "main_accepted_count": 1,
                "qa_review_completed_count": 1,
                "qa_pass_count": 1,
                "qa_yield_percent": 100.0,
            },
            "agents": [{
                "agent_id": "implementation-builder",
                "outcomes": {"completed_lane_count": 1, "main_accepted_count": 1},
            }],
            "billing_semantics": {"api_equivalent_is_not_invoice": True, "actual_billed_cost_usd": None},
            "oauth_capacity_advisory": {"automatic_action_allowed": False},
        }
        write_json(token_budget, budget_payload)
        payload = module.build_payload(token_usage, token_budget, contract_dir)
        fleet = payload["fleet_efficiency"]
        assert fleet["status"] == "outcome_telemetry_unavailable"
        assert fleet["summary"]["completed_lane_count"] is None
        assert fleet["summary"]["main_accepted_count"] is None
        assert fleet["summary"]["qa_yield_percent"] is None
        assert fleet["agents"][0]["outcomes"]["completed_lane_count"] is None
        assert fleet["interpretation"]["outcome_telemetry_creditable"] is False
        assert any(row["id"] == "repair-isolated-agent-outcome-telemetry" for row in payload["action_items"])
        assert "fleet_outcome_telemetry_unavailable" in payload["validation"]["warnings"]


def test_scorecard_missing_fleet_is_unavailable_not_zero() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        token_usage, token_budget, contract_dir = seed(
            Path(tmpdir), module, implementation_gap_count=0, failed_count=0
        )
        payload = module.build_payload(token_usage, token_budget, contract_dir)
        assert payload["fleet_efficiency"]["present"] is False
        assert payload["fleet_efficiency"]["status"] == "unavailable"
        assert payload["fleet_efficiency"]["usage_windows"]["rolling_5h_observed"]["total_tokens"] is None
        assert payload["fleet_efficiency"]["usage_windows"]["rolling_24h_gateway"]["total_tokens"] is None
        assert payload["fleet_efficiency"]["usage_windows"]["closed_7d_gateway"]["total_tokens"] is None
        assert payload["summary"]["fleet_utilized_agent_count"] is None
        assert payload["summary"]["fleet_parent_job_completed_count"] is None
        assert payload["summary"]["fleet_main_accepted_count"] is None
        assert payload["summary"]["fleet_qa_yield_percent"] is None
        assert payload["summary"]["fleet_rework_count"] is None
        assert payload["summary"]["fleet_attribution_gap_count"] is None
        assert any(row["id"] == "refresh-isolated-agent-fleet-reporting" for row in payload["action_items"])


if __name__ == "__main__":
    test_scorecard_surfaces_api_reduction_and_gap_actions()
    test_scorecard_can_be_clean_when_no_gaps_or_failures()
    test_scorecard_propagates_oauth_fields_aliases_and_markdown_labels()
    test_quota_tier_actions_are_advisory_and_complete()
    test_scorecard_missing_or_stale_quota_warns_without_blocking()
    test_high_burn_oauth_capacity_preflight_states_are_advisory_only()
    test_scorecard_attaches_safe_preflight_only_to_repeated_high_burn_candidates()
    test_stale_or_missing_high_burn_preflight_never_blocks_or_dispatches()
    test_scorecard_blocks_bill_conflation_and_automatic_quota_action()
    test_scorecard_normalizes_core_capacity_field_names()
    test_partial_pricing_coverage_never_becomes_a_fake_per_run_average()
    test_scorecard_integrates_fleet_outcomes_without_leaking_content()
    test_scorecard_never_uses_legacy_fleet_completion_fields_as_outcome_credit()
    test_scorecard_missing_fleet_is_unavailable_not_zero()
    print("token efficiency scorecard tests passed")
