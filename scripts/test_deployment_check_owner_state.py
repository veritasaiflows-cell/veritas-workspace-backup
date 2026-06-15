from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from deployment_check import classify


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_deployed_in_band_becomes_deployable(errors: list[str]) -> None:
    state, reason = classify(
        {"close": 401.51, "in_entry_band": True, "below_stop": False, "notes": []},
        blocked=False,
        meta={"workflow_state": "DEPLOYED", "coverage_lane": "execution", "entry_policy": "band_defined"},
    )
    expect(state == "DEPLOYABLE NOW", f"DEPLOYED in-band setup should be deployable-now, got {state}: {reason}", errors)
    expect("owner-approved" in reason, f"DEPLOYED reason should preserve owner-approved context, got {reason}", errors)


def test_deployed_outside_band_fails_closed_to_almost(errors: list[str]) -> None:
    state, reason = classify(
        {"close": 302.10, "in_entry_band": False, "below_stop": False, "notes": []},
        blocked=False,
        meta={"workflow_state": "DEPLOYED", "coverage_lane": "execution", "entry_policy": "band_defined"},
    )
    expect(state == "ALMOST DEPLOYABLE", f"DEPLOYED outside-band setup should fail closed to almost, got {state}: {reason}", errors)
    expect("outside the live entry band" in reason, f"outside-band reason should be explicit, got {reason}", errors)


def test_below_stop_still_overrides_deployed(errors: list[str]) -> None:
    state, reason = classify(
        {"close": 299.0, "in_entry_band": False, "below_stop": True, "notes": []},
        blocked=False,
        meta={"workflow_state": "DEPLOYED", "coverage_lane": "execution", "entry_policy": "band_defined"},
    )
    expect(state == "BELOW STOP", f"below stop must override DEPLOYED, got {state}: {reason}", errors)


def test_almost_in_band_still_requires_promotion_review(errors: list[str]) -> None:
    state, reason = classify(
        {"close": 401.51, "in_entry_band": True, "below_stop": False, "notes": []},
        blocked=False,
        meta={"workflow_state": "ALMOST", "coverage_lane": "execution", "entry_policy": "band_defined"},
    )
    expect(state == "PROMOTION REVIEW", f"ALMOST in-band setup should remain promotion-review, got {state}: {reason}", errors)


def test_almost_in_old_band_with_reclaim_debt_stays_almost(errors: list[str]) -> None:
    state, reason = classify(
        {"close": 300.96, "in_entry_band": True, "below_stop": False, "notes": []},
        blocked=False,
        meta={
            "workflow_state": "ALMOST",
            "coverage_lane": "execution",
            "entry_policy": "band_defined",
            "_band_proposal": {
                "canonical_apply_eligible": False,
                "band_status": "RECLAIM_ONLY",
                "suggested_band_low": 303.67,
                "suggested_band_high": 311.37,
                "suggested_stop": 297.51,
            },
        },
    )
    expect(state == "ALMOST DEPLOYABLE", f"ALMOST with active reclaim-band debt should stay almost, got {state}: {reason}", errors)
    expect("formal reclaim band is not live" in reason, f"reclaim-band reason should be explicit, got {reason}", errors)


def test_portfolio_review_in_band_never_becomes_deployable(errors: list[str]) -> None:
    state, reason = classify(
        {"close": 506.11, "in_entry_band": True, "below_stop": False, "notes": []},
        blocked=False,
        meta={"workflow_state": "PROMOTION REVIEW", "coverage_lane": "watch", "entry_policy": "band_defined"},
    )
    expect(state == "PROMOTION REVIEW", f"PROMOTION REVIEW in-band setup must not become deployable-now, got {state}: {reason}", errors)
    expect("portfolio-review only" in reason, f"PROMOTION REVIEW reason should preserve review-only boundary, got {reason}", errors)


def main() -> int:
    errors: list[str] = []
    test_deployed_in_band_becomes_deployable(errors)
    test_deployed_outside_band_fails_closed_to_almost(errors)
    test_below_stop_still_overrides_deployed(errors)
    test_almost_in_band_still_requires_promotion_review(errors)
    test_almost_in_old_band_with_reclaim_debt_stays_almost(errors)
    test_portfolio_review_in_band_never_becomes_deployable(errors)
    if errors:
        print("deployment_check_owner_state_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("deployment_check_owner_state_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
