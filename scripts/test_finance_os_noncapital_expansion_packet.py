from __future__ import annotations

import finance_os_noncapital_expansion_packet as finance_packet


def test_finance_os_noncapital_expansion_packet_blocks_capital_authority() -> None:
    artifacts = {
        "status_card": {
            "wf78_visibility": {
                "actionable_now_count": 2,
                "owner_review_ready_count": 1,
            }
        },
        "wf78_auto_tier_routing": {
            "summary": {"candidate_count": 1},
            "routing_candidates": [{"ticker": "VRT"}],
        },
        "wf78_clean_tier_roster": {
            "summary": {"tier_a_count": 1},
            "tickers": [{"ticker": "ETN"}],
        },
        "wf78_truth_layer_map": {},
        "canonical_finance_data_plane": {},
        "trade_grade_full_answer_assembler": {},
        "workspace_automation_approval": {},
    }

    packet = finance_packet.build_packet(artifacts)

    assert packet["schema"] == "veritas.finance_os_noncapital_expansion_packet.v1"
    assert packet["validation"]["status"] == "ok"
    assert packet["summary"]["queue_count"] == 3
    assert packet["summary"]["capital_deployment_approved"] is False
    assert packet["summary"]["trade_or_execution_approved"] is False

    queue = packet["expansion_queue"]
    assert queue[0]["candidate_tickers_preview"] == ["VRT"]
    assert "No canon/portfolio mutation." in queue[0]["blocked_actions"]

    boundary = packet["authority_boundary"]
    for flag in (
        "canon_or_portfolio_mutation_allowed",
        "cash_sizing_risk_mutation_allowed",
        "capital_deployment_approved",
        "trade_or_execution_approved",
        "paper_or_live_execution_allowed",
        "brokerage_or_account_action_allowed",
        "owner_approval_inferred",
    ):
        assert boundary[flag] is False, flag
