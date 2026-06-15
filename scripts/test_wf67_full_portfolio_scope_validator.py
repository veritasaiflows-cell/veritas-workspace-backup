from __future__ import annotations

import copy

import wf67_full_portfolio_scope_validator as validator


def base_scope() -> dict:
    return {
        "schema_version": 1,
        "workflow": validator.WORKFLOW,
        "phase": validator.PHASE,
        "artifact_type": "wf67_full_portfolio_paper_scope",
        "scope_id": "wf67-full-portfolio-20260517-v1",
        "approval_status": "review_ready_pending_owner_approval",
        "owner_approval_granted": False,
        "authority": {
            "paper_only": True,
            "paper_endpoint_required": True,
            "paper_endpoint": validator.PAPER_ENDPOINT,
            "paper_credentials_only": True,
            "paper_submit_allowed": True,
            "paper_cancel_allowed": True,
            "dry_run_basket_generation_allowed": True,
            "basket_submit_allowed": False,
            "dry_run_first_required": True,
            "explicit_owner_confirm_after_dry_run_required": True,
            "wf67_guard_required": True,
            "wf63_isolation_required": True,
            "kill_switch_required": True,
            "redacted_audit_required": True,
            "wf55_outcome_logging_required": True,
            "live_submit_allowed": False,
            "live_cancel_allowed": False,
            "live_endpoint_allowed": False,
            "live_credentials_allowed": False,
            "money_movement_allowed": False,
            "account_settings_mutation_allowed": False,
            "replace_order_allowed": False,
            "close_position_allowed": False,
            "liquidation_allowed": False,
            "short_sales_allowed": False,
            "margin_allowed": False,
            "leverage_allowed": False,
            "options_allowed": False,
            "crypto_allowed": False,
            "market_orders_allowed": False,
            "multi_leg_orders_allowed": False,
            "paper_results_promote_to_live_allowed": False,
            "owner_approval_inferred_from_validation": False,
            "execution_authorized": False,
        },
        "portfolio_model": {
            "model_notional_usd": 100000.0,
            "model_notional_role": "ceiling_not_deployment_target",
            "cash_unallocated_allowed": True,
            "target_sleeves": [
                {"sleeve": "stock_quality", "target_notional_usd": 54000.0},
                {"sleeve": "equity_etf", "target_notional_usd": 36000.0},
            ],
        },
        "tranche_controls": {
            "tranche_count": 5,
            "max_tranche_notional_usd": 20000.0,
            "max_total_submitted_notional_per_day_usd": 20000.0,
            "max_aggregate_open_order_notional_usd": 20000.0,
            "post_submit_reconciliation_required": True,
            "post_close_reconciliation_required": True,
            "wf55_outcome_logging_required": True,
        },
        "allowed_symbols": [
            {
                "symbol": symbol,
                "allowed_side": "buy",
                "max_order_notional_usd": 5000.0,
                "max_cumulative_notional_usd": 5000.0,
                "entry_band_required": True,
                "limit_price_required": True,
                "no_chase_required": True,
                "fresh_source_required": True,
                "technical_state_required": "not_below_stop_or_repair",
                "owner_confirmation_required": True,
            }
            for symbol in sorted(validator.REQUIRED_ALLOWED_SYMBOLS)
        ],
        "blocked_symbols": sorted(validator.REQUIRED_BLOCKED_SYMBOLS),
        "order_constraints": {
            "allowed_order_types": ["limit"],
            "allowed_time_in_force": ["day"],
            "regular_hours_only": True,
            "extended_hours_allowed": False,
            "market_orders_allowed": False,
            "buy_only_initial_scope": True,
            "sell_allowed": False,
            "replace_allowed": False,
            "cancel_allowed_for_scope_order_ids_only": True,
        },
    }


def base_basket(scope_id: str) -> dict:
    return {
        "schema_version": 1,
        "workflow": validator.WORKFLOW,
        "artifact_type": "wf67_paper_basket_request",
        "request_id": "wf67-basket-tranche0-dry-run",
        "portfolio_scope_id": scope_id,
        "execution_mode": "dry_run_only",
        "authority": {
            "paper_only": True,
            "dry_run_only": True,
            "live_endpoint_forbidden": True,
            "no_inferred_approval": True,
            "owner_approval_granted": False,
            "execute_allowed": False,
            "live_submit_allowed": False,
            "live_cancel_allowed": False,
            "money_movement_allowed": False,
            "account_settings_mutation_allowed": False,
        },
        "tranche": {"tranche_number": 0, "max_new_submitted_notional_usd": 0.0},
        "orders": [],
        "risk_check": {"status": "ok", "basket_estimated_notional_usd": 0.0},
    }


def findings_for(scope: dict, basket: dict | None = None) -> list[dict]:
    findings: list[dict] = []
    validator.validate_scope(scope, findings)
    if basket is not None:
        validator.validate_basket(basket, scope, findings)
    return findings


def test_valid_review_scope_and_tranche0_basket() -> None:
    scope = base_scope()
    basket = base_basket(scope["scope_id"])
    assert findings_for(scope, basket) == []


def test_live_or_execution_authority_blocks() -> None:
    scope = base_scope()
    scope["authority"]["live_submit_allowed"] = True
    assert any(f["code"] == "scope_authority_false_missing" for f in findings_for(scope))

    scope = base_scope()
    scope["authority"]["execution_authorized"] = True
    assert any(f["code"] == "scope_authority_false_missing" for f in findings_for(scope))


def test_extra_or_blocked_symbol_blocks() -> None:
    scope = base_scope()
    scope["allowed_symbols"].append(copy.deepcopy(scope["allowed_symbols"][0]) | {"symbol": "MSFT"})
    assert any(f["code"] == "scope_extra_allowed_symbols" for f in findings_for(scope))

    scope = base_scope()
    scope["blocked_symbols"].remove("HYG")
    assert any(f["code"] == "scope_missing_blocked_symbols" for f in findings_for(scope))


def test_unexpected_fixed_sleeve_target_blocks() -> None:
    scope = base_scope()
    scope["portfolio_model"]["target_sleeves"].append({"sleeve": "reserve_cash_like_bonds", "target_notional_usd": 9000.0})
    assert any(f["code"] == "scope_unexpected_fixed_sleeve_target" for f in findings_for(scope))


def test_tranche0_basket_cannot_contain_orders_or_execute() -> None:
    scope = base_scope()
    basket = base_basket(scope["scope_id"])
    basket["orders"] = [{"symbol": "SGOV", "side": "buy", "notional": 100.0}]
    assert any(f["code"] == "basket_tranche0_must_have_no_orders" for f in findings_for(scope, basket))

    basket = base_basket(scope["scope_id"])
    basket["authority"]["execute_allowed"] = True
    assert any(f["code"] == "basket_authority_false_missing" for f in findings_for(scope, basket))


if __name__ == "__main__":
    test_valid_review_scope_and_tranche0_basket()
    test_live_or_execution_authority_blocks()
    test_extra_or_blocked_symbol_blocks()
    test_unexpected_fixed_sleeve_target_blocks()
    test_tranche0_basket_cannot_contain_orders_or_execute()
    print("wf67_full_portfolio_scope_validator_tests_passed")
