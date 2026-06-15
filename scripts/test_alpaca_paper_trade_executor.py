from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path

import alpaca_paper_trade_executor as wrapper


def expect_block(fn, code_part: str) -> None:
    try:
        fn()
    except wrapper.BlockedRun as exc:
        assert code_part in str(exc), str(exc)
        return
    raise AssertionError(f"expected BlockedRun containing {code_part}")


def test_trade_request_scope() -> None:
    req = wrapper.sample_trade_request()
    assert wrapper.validate_trade_request(req) == "ok"

    gtc = copy.deepcopy(req)
    gtc["order"]["time_in_force"] = "gtc"
    assert wrapper.validate_trade_request(gtc) == "ok"

    bad = copy.deepcopy(req)
    bad["order"]["type"] = "market"
    expect_block(lambda: wrapper.validate_trade_request(bad), "request_market_order_missing_explicit_owner_approval")

    bad = copy.deepcopy(req)
    bad["order"]["time_in_force"] = "ioc"
    expect_block(lambda: wrapper.validate_trade_request(bad), "request_order_scope_not_limit_or_market_day_or_gtc")

    bad = copy.deepcopy(req)
    bad["order"]["type"] = "market"
    bad["order"]["time_in_force"] = "gtc"
    bad["order"]["limit_price"] = None
    bad["source"]["market_order_owner_approved"] = True
    expect_block(lambda: wrapper.validate_trade_request(bad), "request_gtc_requires_limit_order")

    bad = copy.deepcopy(req)
    bad["order"]["notional"] = 100
    expect_block(lambda: wrapper.validate_trade_request(bad), "request_exactly_one_qty_or_notional_required")

    bad = copy.deepcopy(req)
    bad["source"]["scoped_paper_trade_or_pilot"] = False
    expect_block(lambda: wrapper.validate_trade_request(bad), "scoped_paper_trade_or_pilot_missing")

    bad = copy.deepcopy(req)
    bad["order"]["qty"] = 2
    expect_block(lambda: wrapper.validate_trade_request(bad), "request_qty_exceeds_pilot_cap")

    bad = copy.deepcopy(req)
    bad["order"]["limit_price"] = wrapper.MAX_PILOT_NOTIONAL_USD + 1
    expect_block(lambda: wrapper.validate_trade_request(bad), "request_notional_exceeds_pilot_cap")

    bad = copy.deepcopy(req)
    bad["risk_check"] = {"status": "ok"}
    expect_block(lambda: wrapper.validate_trade_request(bad), "request_position_size_not_reviewed")

    bad = copy.deepcopy(req)
    del bad["authority"]["live_cancel_allowed"]
    expect_block(lambda: wrapper.validate_trade_request(bad), "request_authority_false_missing")


def test_cancel_request_scope() -> None:
    req = wrapper.sample_cancel_request()
    assert wrapper.validate_cancel_request(req) == "ok"

    bad = copy.deepcopy(req)
    bad["cancel"]["paper_order_id"] = ""
    expect_block(lambda: wrapper.validate_cancel_request(bad), "cancel_order_id_missing")

    bad = copy.deepcopy(req)
    bad["authority"]["live_cancel_allowed"] = True
    expect_block(lambda: wrapper.validate_cancel_request(bad), "request_authority_false_missing")


def test_kill_switch_requires_wf67_and_paper_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "kill-switch.json"
        payload = wrapper.create_execution_kill_switch(path, expires_minutes=5, approval_note="test")
        assert wrapper.validate_kill_switch(payload, action="submit") == "ok"
        assert wrapper.validate_kill_switch(payload, action="cancel") == "ok"

        bad = dict(payload)
        bad["live_submit_enabled"] = True
        expect_block(lambda: wrapper.validate_kill_switch(bad, action="submit"), "kill_switch_live_enabled")

        bad = dict(payload)
        bad["endpoint"] = "https://" + "api.alpaca.markets"
        expect_block(lambda: wrapper.validate_kill_switch(bad, action="submit"), "kill_switch_endpoint_not_exact_paper")


def test_sample_requests_cannot_execute() -> None:
    expect_block(lambda: wrapper.validate_not_sample_for_execute(wrapper.sample_trade_request()), "sample_request_cannot_execute")
    expect_block(lambda: wrapper.validate_not_sample_for_execute(wrapper.sample_cancel_request()), "sample_request_cannot_execute")


def test_exact_order_owner_approval_required_for_execute() -> None:
    req = wrapper.sample_trade_request()
    req["request_id"] = "wf67-test-realistic-request"
    req["source"]["owner_or_pilot_scope"] = "test scoped paper order"
    expect_block(lambda: wrapper.validate_exact_order_owner_approval_for_execute(req), "exact_order_owner_approval_missing_for_execute")

    req["source"]["exact_order_owner_approval_status"] = "approved_exact_order"
    req["source"]["approved_by"] = "Randall"
    req["source"]["exact_order_owner_approval_text"] = "Randall approved this exact paper order for test validation only."
    assert wrapper.validate_exact_order_owner_approval_for_execute(req) == "ok"


def test_credentials_reject_ambiguous_names() -> None:
    old = {k: os.environ.get(k) for k in [wrapper.KEY_ENV, wrapper.SECRET_ENV, "APCA_API_KEY_ID"]}
    try:
        os.environ[wrapper.KEY_ENV] = "paper-key-placeholder"
        os.environ[wrapper.SECRET_ENV] = "paper-secret-placeholder"
        os.environ["APCA_API_KEY_ID"] = "ambiguous-placeholder"
        expect_block(wrapper.validate_credentials, "ambiguous_or_live_credential_names_present")
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


if __name__ == "__main__":
    test_trade_request_scope()
    test_cancel_request_scope()
    test_kill_switch_requires_wf67_and_paper_only()
    test_sample_requests_cannot_execute()
    test_exact_order_owner_approval_required_for_execute()
    test_credentials_reject_ambiguous_names()
    print("alpaca_paper_trade_executor_tests_passed")
