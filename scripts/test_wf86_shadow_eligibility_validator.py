from __future__ import annotations

from unittest.mock import patch

import wf86_shadow_eligibility_validator as validator


def test_technical_setup_labels_clean_tactical_and_broken() -> None:
    clean = validator.technical_setup_from_card({
        "technical_posture": {
            "above_ma20": True,
            "above_ma50": True,
            "above_ma200": True,
            "latest_close": 110.0,
            "ma20": 100.0,
            "ma50": 95.0,
            "ma200": 80.0,
        }
    })
    tactical = validator.technical_setup_from_card({
        "technical_posture": {
            "above_ma20": False,
            "above_ma50": False,
            "above_ma200": True,
            "latest_close": 96.0,
            "ma20": 100.0,
            "ma50": 105.0,
            "ma200": 80.0,
        }
    })
    broken = validator.technical_setup_from_card({
        "technical_posture": {
            "above_ma20": True,
            "above_ma50": True,
            "above_ma200": False,
            "latest_close": 75.0,
            "ma20": 70.0,
            "ma50": 72.0,
            "ma200": 80.0,
        }
    })

    assert clean["setup_label"] == "CLEAN_ADD"
    assert clean["notional_multiplier"] == 1.0
    assert tactical["setup_label"] == "TACTICAL_DIP_RECLAIM"
    assert tactical["notional_multiplier"] == 0.30
    assert broken["setup_label"] == "BROKEN_SETUP"
    assert broken["blocker"] == "below_200d_ma"


def test_classify_decision_blocks_unclean_technical_setup_without_execution_authority() -> None:
    unknown = validator.technical_setup_from_card({})
    action, shadow_blockers, assisted_blockers = validator.classify_decision(
        {"current_band_status": "IN_BAND"},
        {},
        {},
        None,
        unknown,
    )

    assert action == "repair_only_technical_setup"
    assert shadow_blockers == ["technical_posture_missing"]
    assert assisted_blockers == []


def test_setup_notional_caps_keep_tactical_smaller_than_absolute_order_ceiling() -> None:
    caps = {
        "max_notional_per_order_usd": 5000,
        "setup_notional_caps_usd": {
            "CLEAN_ADD": 2500,
            "TACTICAL_DIP_RECLAIM": 1500,
        },
    }

    assert validator.setup_notional_cap_usd(caps, "CLEAN_ADD", 5000, 1.0) == 2500.0
    assert validator.setup_notional_cap_usd(caps, "TACTICAL_DIP_RECLAIM", 5000, 0.30) == 1500.0


def test_plain_english_blockers_include_factory_root_cause() -> None:
    factory_row = {
        "root_cause_blockers": ["entry_band_review", "starter_sizing_review"],
        "plain_english_blockers": [
            "NVDA was in band, but could not be promoted because the opportunity-review layer still carried unresolved promotion-review debt: band calibration / AI-power crowding / starter sizing."
        ],
    }
    technical_setup = {
        "setup_label": "TACTICAL_DIP_RECLAIM",
        "reclaim_trigger": "Upgrade after reclaiming the 20D/50D zone near 212.31.",
    }
    plain = validator.plain_english_blockers_for(
        "NVDA",
        factory_row,
        [],
        ["promotion_gate_vetoes_present"],
        technical_setup,
    )
    joined = " ".join(plain)
    assert "NVDA was in band" in joined
    assert "promotion-review debt" in joined
    assert "20D/50D" in joined


def test_no_shadow_decisions_is_fail_closed_warning_not_validation_error() -> None:
    policy = {
        "mode": "shadow_first_no_execution",
        "authority_boundary": {"autonomous_paper_execution_allowed_now": False},
        "initial_caps": {
            "model_portfolio_ceiling_usd": 100000,
            "max_notional_per_order_usd": 5000,
            "setup_notional_caps_usd": {
                "CLEAN_ADD": 2500,
                "TACTICAL_DIP_RECLAIM": 1500,
            },
        },
        "phase_1_decisions": {
            "autonomous_buy_universe_initial": "Tier A only",
            "shadow_min_market_sessions": 5,
            "shadow_min_clean_decisions": 20,
        },
    }

    def fake_load(path):
        return policy if path == validator.POLICY else {}

    with patch.object(validator, "load_dict", side_effect=fake_load):
        report = validator.build_report()

    assert report["status"] == "ok"
    assert report["validation"]["status"] == "ok"
    assert "no_shadow_decisions" in report["validation"]["warnings"]
    assert report["summary"]["execution_ready_count"] == 0


if __name__ == "__main__":
    test_technical_setup_labels_clean_tactical_and_broken()
    test_classify_decision_blocks_unclean_technical_setup_without_execution_authority()
    test_setup_notional_caps_keep_tactical_smaller_than_absolute_order_ceiling()
    test_plain_english_blockers_include_factory_root_cause()
    test_no_shadow_decisions_is_fail_closed_warning_not_validation_error()
    print("wf86_shadow_eligibility_validator_tests_passed")
