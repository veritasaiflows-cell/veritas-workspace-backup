from __future__ import annotations

from pathlib import Path

import alpaca_paper_trade_executor as wf67
import wf67_order_card_request_generator as gen


POLICY = "tmp/paper-autotrader/policy.json"


def base_request(max_notional: float = 5000.0) -> dict:
    return {
        "schema_version": 1,
        "workflow": "WF67 - Alpaca Paper Execution Guardrail",
        "artifact_type": "wf67_paper_trade_request",
        "request_id": "wf67-wf86-cap-bridge-test",
        "created_at_utc": "2026-06-11T17:00:00Z",
        "authority": {
            "paper_only": True,
            "paper_submit_allowed": True,
            "paper_cancel_allowed": True,
            "live_submit_allowed": False,
            "live_cancel_allowed": False,
            "live_endpoint_forbidden": True,
            "money_movement_allowed": False,
            "account_settings_mutation_allowed": False,
            "no_inferred_approval": True,
        },
        "order": {
            "symbol": "VRT",
            "side": "buy",
            "type": "limit",
            "time_in_force": "day",
            "limit_price": 290.0,
            "qty": None,
            "notional": 1000.0,
        },
        "risk_check": {
            "status": "ok",
            "estimated_notional_usd": 1000.0,
            "max_loss_usd": 1000.0,
            "max_notional_usd": max_notional,
            "position_size_reviewed": True,
            "pilot_qty_cap": 1,
            "pilot_notional_cap_usd": max_notional,
            "full_scope_artifact": POLICY,
        },
        "source": {
            "scoped_paper_trade_or_pilot": True,
            "owner_or_pilot_scope": "WF86 cap bridge validation only; no execution approval.",
            "recommendation_source": "test",
            "market_order_owner_approved": False,
            "exact_order_owner_approval_status": "pending_exact_randall_approval",
        },
        "audit": {
            "secret_material_present": False,
            "raw_response_persistence_allowed": False,
            "redaction_required": True,
            "paper_endpoint": "https://paper-api.alpaca.markets",
            "live_endpoint_forbidden": "https://api.alpaca.markets",
        },
    }


def expect_blocked(request: dict, text: str) -> None:
    try:
        wf67.validate_trade_request(request)
    except wf67.BlockedRun as exc:
        assert text in str(exc), str(exc)
        return
    raise AssertionError(f"expected BlockedRun containing {text}")


def test_oversize_request_requires_full_scope_artifact() -> None:
    request = base_request()
    request["risk_check"].pop("full_scope_artifact")
    request["risk_check"]["pilot_notional_cap_usd"] = 500.0
    expect_blocked(request, "request_notional_exceeds_pilot_cap")


def test_wf86_policy_allows_non_executing_5000_request_validation() -> None:
    request = base_request()
    assert wf67.validate_trade_request(request) == "ok"
    try:
        wf67.validate_exact_order_owner_approval_for_execute(request)
    except wf67.BlockedRun as exc:
        assert "exact_order_owner_approval_missing_for_execute" in str(exc)
    else:
        raise AssertionError("cap bridge must not bypass exact owner approval")


def test_request_generator_carries_full_scope_cap() -> None:
    card = {
        "schema_version": 1,
        "artifact_type": "main_session_wf67_order_decision_card",
        "request_id": "wf67-wf86-card-cap-bridge-test",
        "authority": {
            "main_session_recommendation_allowed": True,
            "wf67_request_artifact_generation_allowed": True,
            "paper_only": True,
            "paper_order_execution_allowed_by_card": False,
            "live_trade_allowed": False,
            "owner_approval_inferred": False,
            "portfolio_or_canon_apply_allowed": False,
            "cash_or_risk_rule_mutation_allowed": False,
        },
        "order": {"symbol": "VRT", "side": "buy", "type": "limit", "time_in_force": "day", "limit_price": 290.0, "qty": None, "notional": 1000.0},
        "risk_check": {
            "status": "ok",
            "estimated_notional_usd": 1000.0,
            "max_loss_usd": 1000.0,
            "max_notional_usd": 5000.0,
            "entry_band_low": 265.9,
            "entry_band_high": 318.35,
            "observed_price": 289.185,
            "observed_entry_status": "IN_BAND",
            "stop": 242.07,
            "sizing_rationale": "WF86 cap bridge validation only.",
            "full_scope_artifact": POLICY,
        },
        "source": {
            "source_artifact": "tmp/paper-autotrader/shadow-eligibility.json",
            "owner_or_pilot_scope": "WF86 cap bridge validation only; no execution approval.",
        },
        "owner_approval": {"status": "pending_exact_randall_approval"},
    }
    request = gen.build_request(card, card_path=Path("tmp/card.json"))
    assert request["risk_check"]["pilot_notional_cap_usd"] == 5000.0
    assert request["risk_check"]["full_scope_artifact"] == POLICY
    assert wf67.validate_trade_request(request) == "ok"


if __name__ == "__main__":
    test_oversize_request_requires_full_scope_artifact()
    test_wf86_policy_allows_non_executing_5000_request_validation()
    test_request_generator_carries_full_scope_cap()
    print("wf67_wf86_cap_bridge_tests_passed")
