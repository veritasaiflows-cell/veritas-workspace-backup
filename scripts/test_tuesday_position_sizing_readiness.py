#!/usr/bin/env python3
"""Focused tests for position-sizing readiness classification."""
from __future__ import annotations

import tuesday_position_sizing_readiness as sizing


def test_no_capital_packet_warning_is_review_only() -> None:
    validation = {
        "status": "warning",
        "summary": {"critical": 0, "warning": 1},
        "findings": [
            {
                "severity": "warning",
                "issue": "no capital recommendation packets produced for this window",
            }
        ],
    }

    assert sizing.capital_validator_no_candidate_warning(validation) is True


def test_nonzero_capital_validator_critical_still_blocks() -> None:
    validation = {
        "status": "warning",
        "summary": {"critical": 1, "warning": 1},
        "findings": [
            {
                "severity": "warning",
                "issue": "no capital recommendation packets produced for this window",
            }
        ],
    }

    assert sizing.capital_validator_no_candidate_warning(validation) is False


def test_other_capital_validator_warning_still_blocks() -> None:
    validation = {
        "status": "warning",
        "summary": {"critical": 0, "warning": 1},
        "findings": [{"severity": "warning", "issue": "unexpected warning"}],
    }

    assert sizing.capital_validator_no_candidate_warning(validation) is False


if __name__ == "__main__":
    test_no_capital_packet_warning_is_review_only()
    test_nonzero_capital_validator_critical_still_blocks()
    test_other_capital_validator_warning_still_blocks()
    print("tuesday_position_sizing_readiness targeted tests passed")
