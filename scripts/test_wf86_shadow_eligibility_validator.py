from __future__ import annotations

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


if __name__ == "__main__":
    test_technical_setup_labels_clean_tactical_and_broken()
    test_classify_decision_blocks_unclean_technical_setup_without_execution_authority()
    test_setup_notional_caps_keep_tactical_smaller_than_absolute_order_ceiling()
    print("wf86_shadow_eligibility_validator_tests_passed")
