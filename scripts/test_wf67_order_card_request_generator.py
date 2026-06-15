from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import wf67_order_card_request_generator as gen
import alpaca_paper_trade_executor as wf67


def base_card() -> dict:
    return {
        "schema_version": 1,
        "artifact_type": "main_session_wf67_order_decision_card",
        "request_id": "wf67-main-card-etn-test",
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
        "order": {"symbol": "ETN", "side": "buy", "type": "limit", "time_in_force": "day", "limit_price": 391.35, "qty": None, "notional": 100.0},
        "risk_check": {
            "status": "ok",
            "estimated_notional_usd": 100.0,
            "max_loss_usd": 100.0,
            "max_notional_usd": 125.0,
            "entry_band_low": 356.99,
            "entry_band_high": 400.66,
            "observed_price": 391.35,
            "observed_entry_status": "IN_BAND",
            "stop": 337.14,
            "sizing_rationale": "ETN optional incremental starter top-up; existing 1 paper share already counts as starter exposure.",
        },
        "source": {
            "source_artifact": "tmp/tuesday-position-sizing-readiness-2026-05-26.json",
            "capital_recommendation_source": "tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json",
            "owner_or_pilot_scope": "approval-ready ETN paper-order card pending exact Randall approval",
            "approval_artifact": "tmp/alpaca-paper-readiness/phase-7-advisor-paper-execution-approval-2026-05-19.json",
        },
        "owner_approval": {"status": "pending_exact_randall_approval"},
    }


def expect_card_error(card: dict, text: str) -> None:
    try:
        gen.validate_card(card)
    except gen.CardError as exc:
        assert text in str(exc), str(exc)
        return
    raise AssertionError(f"expected CardError containing {text}")


def test_pending_card_builds_request_but_cannot_execute() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "card.json"
        card = base_card()
        path.write_text("{}", encoding="utf-8")
        request = gen.build_request(card, card_path=path)
        assert wf67.validate_trade_request(request) == "ok"
        assert request["source"]["exact_order_owner_approval_status"] == "pending_exact_randall_approval"
        assert request["authority"]["paper_submit_allowed"] is True
        assert request["authority"]["paper_submit_allowed_after_exact_approval_and_guard"] is True
        assert request["authority"]["currently_executable"] is False
        assert request["execution_readiness"]["currently_executable"] is False
        assert request["execution_readiness"]["execution_by_this_artifact_allowed"] is False
        assert request["execution_readiness"]["requires_exact_owner_approval"] is True
        try:
            wf67.validate_exact_order_owner_approval_for_execute(request)
        except wf67.BlockedRun as exc:
            assert "exact_order_owner_approval_missing_for_execute" in str(exc)
        else:
            raise AssertionError("pending request must not be executable")


def test_approved_card_carries_execute_approval_metadata() -> None:
    card = base_card()
    card["owner_approval"] = {
        "status": "approved_exact_order",
        "approved_by": "Randall",
        "approval_text": "Randall approved this exact ETN paper order card for test validation.",
    }
    request = gen.build_request(card, card_path=Path("tmp/card.json"))
    assert wf67.validate_exact_order_owner_approval_for_execute(request) == "ok"


def test_card_rejects_authority_drift_and_oversize() -> None:
    card = base_card()
    bad = copy.deepcopy(card)
    bad["authority"]["live_trade_allowed"] = True
    expect_card_error(bad, "authority_false_missing:live_trade_allowed")

    bad = copy.deepcopy(card)
    bad["risk_check"]["estimated_notional_usd"] = 501
    expect_card_error(bad, "estimated_notional_exceeds_wf67_pilot_cap")


def test_card_rejects_schema_and_execution_surface_drift() -> None:
    card = base_card()
    bad = copy.deepcopy(card)
    bad["schema_version"] = 2
    expect_card_error(bad, "schema_version_must_be_1")

    bad = copy.deepcopy(card)
    bad["kill_switch"] = {"created": True}
    expect_card_error(bad, "forbidden_card_top_level_key:kill_switch")

    bad = copy.deepcopy(card)
    bad["owner_approval"] = {
        "status": "pending_exact_randall_approval",
        "approved_by": "Randall",
        "approval_text": "Looks good",
    }
    expect_card_error(bad, "pending_card_must_not_carry_approval_metadata")


def test_market_order_requires_explicit_exact_approval() -> None:
    card = base_card()
    card["order"] = {"symbol": "ETN", "side": "buy", "type": "market", "time_in_force": "day", "limit_price": None, "qty": 1, "notional": None}
    expect_card_error(card, "market_order_requires_explicit_owner_approval")

    card["owner_approval"] = {
        "status": "approved_exact_order",
        "approved_by": "Randall",
        "approval_text": "Randall approved this exact ETN market paper order card for test validation.",
        "market_order_owner_approved": True,
    }
    request = gen.build_request(card, card_path=Path("tmp/card.json"))
    assert request["source"]["market_order_owner_approved"] is True


def test_required_promotion_gate_blocks_non_promoted_buy() -> None:
    card = base_card()
    with tempfile.TemporaryDirectory() as tmp:
        gate_path = Path(tmp) / "gate.json"
        gate_path.write_text(json.dumps({
            "status": "ok",
            "schema_version": "test",
            "generated_at_utc": "2026-05-31T00:00:00Z",
            "candidates": [{
                "ticker": "ETN",
                "rank": 1,
                "chief_intelligence_score": 80,
                "chief_intelligence_verdict": "monitor_only",
                "band_status": "IN_BAND",
                "vetoes": [],
                "authority": {
                    "paper_order_execution_allowed": False,
                    "owner_approval_inferred": False,
                },
            }],
        }), encoding="utf-8")
        try:
            gen.build_request(card, card_path=Path("tmp/card.json"), promotion_gate_path=gate_path)
        except gen.CardError as exc:
            assert "promotion_gate_verdict_not_buy_ready:ETN:monitor_only" in str(exc), str(exc)
        else:
            raise AssertionError("non-promoted buy must be blocked by required promotion gate")


def test_required_promotion_gate_is_carried_into_request_source() -> None:
    card = base_card()
    with tempfile.TemporaryDirectory() as tmp:
        gate_path = Path(tmp) / "gate.json"
        gate_path.write_text(json.dumps({
            "status": "ok",
            "schema_version": "test",
            "generated_at_utc": "2026-05-31T00:00:00Z",
            "candidates": [{
                "ticker": "ETN",
                "rank": 3,
                "chief_intelligence_score": 83.4,
                "chief_intelligence_verdict": "promote_for_owner_review",
                "band_status": "IN_BAND",
                "vetoes": [],
                "entry_band": {"low": 382.9, "high": 401.36, "stop": 362.67},
                "authority": {
                    "paper_order_execution_allowed": False,
                    "owner_approval_inferred": False,
                },
            }],
        }), encoding="utf-8")
        request = gen.build_request(card, card_path=Path("tmp/card.json"), promotion_gate_path=gate_path)
        gate = request["source"]["chief_intelligence_promotion_gate"]
        assert gate["ticker"] == "ETN"
        assert gate["chief_intelligence_verdict"] == "promote_for_owner_review"


if __name__ == "__main__":
    test_pending_card_builds_request_but_cannot_execute()
    test_approved_card_carries_execute_approval_metadata()
    test_card_rejects_authority_drift_and_oversize()
    test_card_rejects_schema_and_execution_surface_drift()
    test_market_order_requires_explicit_exact_approval()
    test_required_promotion_gate_blocks_non_promoted_buy()
    test_required_promotion_gate_is_carried_into_request_source()
    print("wf67_order_card_request_generator_tests_passed")
