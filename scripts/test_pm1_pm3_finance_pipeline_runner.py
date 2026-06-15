#!/usr/bin/env python3
"""Acceptance tests for pm1_pm3_finance_pipeline_runner.py."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pm1_pm3_finance_pipeline_runner.py"


def load_module():
    spec = importlib.util.spec_from_file_location("pm1_pm3_finance_pipeline_runner", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture_artifacts(module):
    artifacts = {name: {"status": "ok", "generated_at_utc": "2026-06-12T00:00:00Z", "validation": {"status": "ok"}, "summary": {}} for name in module.EXPECTED_ARTIFACTS}
    artifacts["wf78_phase_runner"]["summary"] = {"failed_steps": 0}
    artifacts["wf78_daily_freshness_loop"]["parameters"] = {"skip_provider_refresh": False}
    artifacts["wf78_daily_freshness_loop"]["summary"] = {"failed_steps": []}
    artifacts["wf78_auto_tier_router"]["summary"] = {
        "auto_tier_counts": {"Tier A": 22, "Tier B": 28, "Tier C": 150},
        "auto_state_counts": {"A-READY": 3, "A-CHALLENGED": 15},
        "capital_deployment_approved_count": 0,
        "trade_or_execution_approved_count": 0,
    }
    artifacts["wf84_packet"]["summary"] = {
        "security_master_count": 200,
        "routing_state_current_count": 200,
        "tier_counts": {"Tier A": 22, "Tier B": 28, "Tier C": 150},
        "forbidden_authority_true_count": 0,
    }
    artifacts["wf84_validation"]["status"] = "ok"
    artifacts["wf84_validation"]["summary"] = {"security_master_count": 200}
    artifacts["wf84_phase6_10"]["summary"] = {"critical_error_count": 0, "warning_count": 0}
    artifacts["wf84_wf85_full_answer_parity"]["summary"] = {
        "critical_ticker_count": 0,
        "full_population_covered": True,
    }
    artifacts["wf85_decision_cards"]["summary"] = {
        "card_count": 200,
        "decision_state_counts": {"monitor_only": 200},
        "authority_flags_false_by_contract": True,
    }
    artifacts["wf85_approval_gate"]["summary"] = {
        "review_ready_count": 0,
        "approval_card_draft_count": 0,
        "wf67_paper_guard_fresh": True,
        "wf67_paper_guard_clean": True,
    }
    artifacts["wf85_full_answer_assembler"]["summary"] = {"full_answer_built_count": 200}
    artifacts["trade_grade_os_freshness_runner"]["operator_action"] = "NO_REPLY"
    artifacts["trade_grade_os_freshness_runner"]["summary"] = {
        "full_answer_rebuild": {"mode": "always", "command_run": True}
    }
    artifacts["pm_control_packet"]["summary"] = {
        "pm_readiness": {"readiness_band": "green", "blocked_lanes": 0, "stale_lanes": 0},
        "implementation_queue": {"job_count": 10, "ready_job_count": 9, "blocked_job_count": 0},
        "stale_lane_digest": {"stale_lane_count": 0},
        "top_next_action": {"rank": 1},
    }
    return artifacts


def main() -> int:
    module = load_module()
    artifacts = fixture_artifacts(module)
    payload = module.build_payload([], artifacts, mode="summary-only")
    assert payload["status"] == "ready_for_morning_review"
    assert payload["operator_action"] == "MAIN_REVIEW_READY"
    assert payload["authority_boundary"]["capital_deployment_approved"] is False
    assert payload["authority_boundary"]["paper_or_live_execution_allowed"] is False
    assert payload["authority_boundary"]["owner_approval_inferred"] is False

    bad_authority = copy.deepcopy(artifacts)
    bad_authority["wf78_auto_tier_router"]["summary"]["capital_deployment_approved_count"] = 1
    blocked = module.build_payload([], bad_authority, mode="summary-only")
    assert blocked["status"] == "blocked"
    assert any("wf78_capital_deployment_approved_count_nonzero" in error for error in blocked["validation"]["errors"])

    bad_step = module.build_payload([{"name": "wf78", "ok": False}], artifacts, mode="summary-only")
    assert bad_step["status"] == "blocked"
    assert any("pipeline_step_failed" in error for error in bad_step["validation"]["errors"])

    warning_artifacts = copy.deepcopy(artifacts)
    warning_artifacts["pm_control_packet"]["summary"]["pm_readiness"]["stale_lanes"] = 1
    warning = module.build_payload([], warning_artifacts, mode="summary-only")
    assert warning["status"] == "needs_attention"
    assert warning["operator_action"] == "MAIN_REVIEW_RECOMMENDED"

    no_provider_refresh = copy.deepcopy(artifacts)
    no_provider_refresh["wf78_daily_freshness_loop"]["parameters"]["skip_provider_refresh"] = True
    provider_blocked = module.build_payload([], no_provider_refresh, mode="morning")
    assert provider_blocked["status"] == "blocked"
    assert "wf78_provider_refresh_not_used_for_morning_readiness" in provider_blocked["validation"]["errors"]

    print("pm1_pm3_finance_pipeline_runner_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
