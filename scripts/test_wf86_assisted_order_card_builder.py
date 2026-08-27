from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import wf86_assisted_order_card_builder as builder
import alpaca_paper_trade_executor as wf67


def sample_policy() -> dict:
    return {
        "initial_caps": {
            "max_notional_per_order_usd": 5000,
            "setup_notional_caps_usd": {"TACTICAL_DIP_RECLAIM": 1500},
        },
    }


def sample_decision(*, shadow_decision: str = "would_buy_shadow") -> dict:
    return {
        "ticker": "VRT",
        "shadow_eligible": True,
        "shadow_decision": shadow_decision,
        "assisted_review_blockers": [],
        "execution_blockers": [
            "wf67_guard_not_clean",
            "fresh_kill_switch_not_proven",
            "redacted_audit_and_reconciliation_not_proven",
            "separate_scoped_randall_pilot_approval_missing",
        ],
        "recommended_shadow_notional_usd": 1500,
        "setup_notional_cap_usd": 1500,
        "current_price": 300,
        "current_band_status": "IN_BAND",
        "written_band": {
            "entry_band_low": 275,
            "entry_band_high": 315,
            "stop_or_invalidation": 250,
        },
        "technical_setup": {
            "setup_label": "TACTICAL_DIP_RECLAIM",
            "notional_multiplier": 0.3,
        },
        "opportunity_review": {},
        "wf84_canonical_data_plane": {},
    }


def sample_eligibility(decision: dict | None = None) -> dict:
    row = decision or sample_decision()
    would_buy = [row["ticker"]] if row.get("shadow_decision") == "would_buy_shadow" else []
    return {
        "summary": {
            "candidate_count": 1,
            "would_buy_shadow_tickers": would_buy,
        },
        "decisions": [row],
    }


def test_build_vrt_assisted_card_is_non_executing_and_cap_bridged() -> None:
    policy = sample_policy()
    eligibility = sample_eligibility()
    card = builder.build_card("VRT", policy, eligibility, builder.DEFAULT_POLICY)
    request = builder.wf67_card.build_request(card, card_path=Path("tmp/card.json"))
    assert card["order"]["symbol"] == "VRT"
    assert card["order"]["notional"] == 1500.0
    assert card["risk_check"]["policy_max_notional_usd"] == 5000.0
    assert card["risk_check"]["setup_notional_cap_usd"] == 1500.0
    assert card["risk_check"]["technical_setup_label"] == "TACTICAL_DIP_RECLAIM"
    assert "tactical_dip_reclaim_requires_fresh_exact_owner_review" in card["decision_context"]["assisted_review_blockers"]
    assert card["authority"]["paper_order_execution_allowed_by_card"] is False
    assert request["risk_check"]["pilot_notional_cap_usd"] == 5000.0
    assert request["risk_check"]["estimated_notional_usd"] == 1500.0
    assert request["risk_check"]["full_scope_artifact"] == "tmp/paper-autotrader/policy.json"
    assert wf67.validate_trade_request(request) == "ok"
    try:
        wf67.validate_exact_order_owner_approval_for_execute(request)
    except wf67.BlockedRun as exc:
        assert "exact_order_owner_approval_missing_for_execute" in str(exc), str(exc)
    else:
        raise AssertionError("assisted request must remain blocked for execution")


def test_stale_exact_approval_is_stripped_fail_closed() -> None:
    policy = sample_policy()
    eligibility = sample_eligibility()
    card = builder.build_card("VRT", policy, eligibility, builder.DEFAULT_POLICY)
    approval = deepcopy(builder.load_dict(builder.DEFAULT_APPROVAL))
    approval["approved_order"]["limit_price"] = round(card["order"]["limit_price"] + 1.0, 2)

    blocked = builder.apply_approval_fail_closed(card, approval, Path("tmp/stale-approval.json"))
    blockers = blocked["decision_context"]["assisted_review_blockers"]

    assert blocked["owner_approval"]["status"] == "pending_exact_randall_approval"
    assert blocked["decision_context"]["trade_or_execution_approved"] is False
    assert blocked["decision_context"]["paper_or_live_execution_allowed"] is False
    assert any(item.startswith("stale_or_mismatched_owner_approval:") for item in blockers)


def test_non_candidate_writes_safe_no_card_index() -> None:
    eligibility = sample_eligibility(sample_decision(shadow_decision="no_action_wait_for_band"))
    index = builder.build_no_candidate_index(
        ticker="VRT",
        eligibility=eligibility,
        reason="ticker_not_would_buy_shadow:VRT:no_action_wait_for_band",
        card_path=Path("tmp/card.json"),
        request_path=Path("tmp/request.json"),
    )

    assert index["status"] == "no_current_card_candidate"
    assert index["summary"]["card_count"] == 0
    assert index["summary"]["execution_ready"] is False
    assert index["authority_boundary"]["paper_submit_allowed"] is False
    assert index["authority_boundary"]["live_trade_allowed"] is False
    assert index["validation"]["status"] == "ok"
    assert index["cards"] == []


if __name__ == "__main__":
    test_build_vrt_assisted_card_is_non_executing_and_cap_bridged()
    test_stale_exact_approval_is_stripped_fail_closed()
    test_non_candidate_writes_safe_no_card_index()
    print("wf86_assisted_order_card_builder_tests_passed")
