#!/usr/bin/env python3
"""Tests for the market-open repair cadence packet."""
from __future__ import annotations

import market_open_repair_cadence as cadence


def test_contract_record_accepts_midday_builder_before_radar() -> None:
    rows = [cadence.contract_record(req) for req in cadence.CONTRACT_REQUIREMENTS]
    midday = next(row for row in rows if row["stage"] == "midday_card_rebuild")

    assert midday["status"] == "ok"
    assert not any("ordering_gap" in warning for warning in midday["warnings"])


def test_repair_commands_include_resume_command() -> None:
    summary = {
        "evidence_repair_resume": {
            "next_command": "python scripts\\wf78_evidence_repair_batch_runner.py --tier A --cursor 10 --limit 10 --write --validate"
        }
    }

    commands = cadence.repair_commands(summary)
    stages = [row["stage"] for row in commands]

    assert "source_trust_guard" in stages
    assert "evidence_repair_resume" in stages
    assert "first_settled_quote_probe" in stages
    assert all("--send" not in row["command"] for row in commands)


def test_packet_preserves_authority_boundary() -> None:
    packet = cadence.build_packet()

    assert packet["authority_boundary"]["capital_deployment_allowed"] is False
    assert packet["authority_boundary"]["trade_or_execution_allowed"] is False
    assert packet["authority_boundary"]["mutates_cron_schedule"] is False
    assert packet["validation"]["authority_drift_paths"] == []
    assert packet["repair_command_plan"]


def test_why_not_auto_completed_omits_retired_repair_reasons() -> None:
    reasons = cadence.why_not_auto_completed(
        {
            "morning_cards_status": "warning",
            "morning_cards_validation": "ok",
            "morning_soft_step_failures": [],
            "evidence_repair_resume": {"has_more": False, "remaining_in_tier": 0},
            "tier_a_repair_count": 5,
            "repair_queue_count": 42,
        },
        [],
    )
    joined = " ".join(reasons)

    assert "soft failures" not in joined
    assert "remaining Tier A evidence debt" not in joined
    assert "schedule-order warning" not in joined
    assert "no clean paper-deployment approval cards" in joined
