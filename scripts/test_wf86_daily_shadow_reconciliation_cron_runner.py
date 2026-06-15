#!/usr/bin/env python3
"""Acceptance checks for the WF86 daily shadow/reconciliation cron runner."""
from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent / "wf86_daily_shadow_reconciliation_cron_runner.py"
spec = importlib.util.spec_from_file_location("wf86_daily_shadow_reconciliation_cron_runner", SCRIPT)
assert spec and spec.loader
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_authority_boundary_blocks_execution() -> None:
    boundary = runner.AUTHORITY_BOUNDARY
    assert boundary["review_only"] is True
    assert boundary["shadow_logging_allowed"] is True
    assert boundary["get_only_paper_reconciliation_allowed"] is True
    for key in (
        "autonomous_paper_execution_allowed_now",
        "paper_submit_allowed",
        "paper_cancel_allowed",
        "paper_sell_allowed",
        "paper_replace_allowed",
        "live_trade_allowed",
        "live_endpoint_allowed",
        "brokerage_or_account_action_allowed",
        "money_movement_allowed",
        "portfolio_or_canon_mutation_allowed",
        "owner_approval_inferred",
    ):
        assert boundary[key] is False


def test_command_plan_has_no_executor_submit_cancel_sell() -> None:
    commands = [" ".join(command) for _, command, _, _ in runner.command_plan(skip_paper_reconciliation=False)]
    joined = "\n".join(commands).lower()
    assert "alpaca_paper_trade_executor.py" not in joined
    assert "--execute" not in joined
    assert "alpaca_paper_position_sql_refresh.py refresh" in joined
    assert "alpaca_paper_order_history_classifier.py --write --validate" in joined
    assert "wf86_assisted_order_card_builder.py --write --validate" in joined
    assert "wf86_shadow_decision_ledger.py --write --validate" in joined
    assert "wf87_trade_decision_journal.py --write --validate" in joined
    assert "wf87_position_sizing_runtime_check.py --write --validate" in joined
    assert "wf87_portfolio_circuit_breakers.py --write --validate" in joined
    assert "wf87_approval_freshness_ttl.py --write --validate" in joined
    assert "wf87_intraday_monitor.py --write --validate" in joined
    assert "wf87_assisted_paper_cadence.py --write --validate" in joined
    assert "wf87_shadow_outcome_scorecard.py --write --validate" in joined
    assert "wf87_v2_readiness_rollup.py --write --validate" in joined
    assert "wf87_market_hours_gate_probe.py --skip-refresh --write --validate" in joined
    assert "wf87_autonomy_command_center.py --write --write-md --validate" in joined


def test_validation_rejects_execution_ready() -> None:
    payload = {
        "authority_boundary": dict(runner.AUTHORITY_BOUNDARY),
        "steps": [{"name": "ok", "ok": True}],
        "artifact_records": [{"name": name, "exists": True} for name in runner.EXPECTED_ARTIFACTS],
        "summary": {
            "autonomous_paper_buy_ready": True,
            "shadow_threshold_met": False,
            "post_trade_reconciliation_blocker_present": True,
        },
    }
    validation = runner.validate_payload(payload)
    assert validation["status"] == "error"
    assert "autonomous_paper_buy_ready_unexpectedly_true" in validation["errors"]


def test_fail_closed_reconciliation_boundary_can_continue() -> None:
    payload = {
        "status": "blocked",
        "account_mode": "paper",
        "method": "GET_only",
        "trade_or_account_action_allowed": False,
        "paper_submit_allowed": False,
        "paper_cancel_allowed": False,
        "live_endpoint_detected": False,
        "money_movement_allowed": False,
        "owner_approval_inferred": False,
    }
    assert runner.artifact_preserves_paper_reconciliation_boundary(payload) is True
    payload["paper_submit_allowed"] = True
    assert runner.artifact_preserves_paper_reconciliation_boundary(payload) is False


if __name__ == "__main__":
    test_authority_boundary_blocks_execution()
    test_command_plan_has_no_executor_submit_cancel_sell()
    test_validation_rejects_execution_ready()
    test_fail_closed_reconciliation_boundary_can_continue()
    print("wf86_daily_shadow_reconciliation_cron_runner_tests_passed")
