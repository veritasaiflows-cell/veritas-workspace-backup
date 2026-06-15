from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import wf86_assisted_order_card_builder as builder
import wf86_shadow_eligibility_validator as eligibility_builder
import alpaca_paper_trade_executor as wf67


def test_build_vrt_assisted_card_is_non_executing_and_cap_bridged() -> None:
    policy = builder.load_dict(builder.DEFAULT_POLICY)
    eligibility = eligibility_builder.build_report()
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
    policy = builder.load_dict(builder.DEFAULT_POLICY)
    eligibility = eligibility_builder.build_report()
    card = builder.build_card("VRT", policy, eligibility, builder.DEFAULT_POLICY)
    approval = deepcopy(builder.load_dict(builder.DEFAULT_APPROVAL))
    approval["approved_order"]["limit_price"] = round(card["order"]["limit_price"] + 1.0, 2)

    blocked = builder.apply_approval_fail_closed(card, approval, Path("tmp/stale-approval.json"))
    blockers = blocked["decision_context"]["assisted_review_blockers"]

    assert blocked["owner_approval"]["status"] == "pending_exact_randall_approval"
    assert blocked["decision_context"]["trade_or_execution_approved"] is False
    assert blocked["decision_context"]["paper_or_live_execution_allowed"] is False
    assert any(item.startswith("stale_or_mismatched_owner_approval:") for item in blockers)


if __name__ == "__main__":
    test_build_vrt_assisted_card_is_non_executing_and_cap_bridged()
    test_stale_exact_approval_is_stripped_fail_closed()
    print("wf86_assisted_order_card_builder_tests_passed")
