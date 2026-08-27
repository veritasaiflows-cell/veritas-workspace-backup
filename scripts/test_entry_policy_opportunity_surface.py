from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from band_hygiene_freshness_controller import entry_policy_review_candidate
from deployment_check import classify


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_watch_lane_in_band_surfaces_entry_policy_review(errors: list[str]) -> None:
    state, reason = classify(
        {"close": 183.64, "in_entry_band": True, "below_stop": False, "notes": []},
        blocked=False,
        meta={"workflow_state": "WATCH", "coverage_lane": "watch", "entry_policy": "underdefined"},
    )
    expect(state == "ENTRY POLICY REVIEW", f"watch-lane in-band should surface entry-policy review, got {state}: {reason}", errors)
    expect("no execution-board entitlement" in reason, f"reason must preserve no-execution boundary, got {reason}", errors)


def test_below_stop_still_blocks_entry_policy_review(errors: list[str]) -> None:
    state, reason = classify(
        {"close": 180.40, "in_entry_band": False, "below_stop": True, "notes": []},
        blocked=False,
        meta={"workflow_state": "WATCH", "coverage_lane": "watch", "entry_policy": "underdefined"},
    )
    expect(state == "BELOW STOP", f"below-stop watch name must not become entry-policy review, got {state}: {reason}", errors)


def test_hygiene_candidate_reuses_existing_surfaces(errors: list[str]) -> None:
    candidate = entry_policy_review_candidate(
        "RTX",
        {
            "entry_policy": "underdefined",
            "coverage_lane": "watch",
            "workflow_state": "WATCH",
            "band_status": "NEAR_BAND",
            "current_band_low": 183.01,
            "current_band_high": 193.23,
            "current_stop": 177.91,
            "canonical_apply_eligible": False,
            "reasons": ["non-execution lane proposals are review-only", "entry policy is not band_defined"],
        },
        {"in_entry_band": True, "below_stop": False, "ma_posture": "above all MAs"},
        "exception_owner_review",
        ["quote_not_intraday_fresh", "canonical_apply_eligible is not true"],
    )
    expect(candidate["candidate"] is True, f"RTX-style row should be a review candidate: {candidate}", errors)
    expect(candidate["secondary_not_suppressing"] is True, "secondary/watch role must not suppress visibility", errors)
    expect(candidate["source_fields"]["technical.ma_posture"] == "above all MAs", "candidate should carry sourced MA posture", errors)


def test_hygiene_below_stop_is_repair_first(errors: list[str]) -> None:
    candidate = entry_policy_review_candidate(
        "CVX",
        {
            "entry_policy": "underdefined",
            "coverage_lane": "watch",
            "workflow_state": "WATCH",
            "band_status": "IN_BAND",
            "current_band_low": 186.91,
            "current_band_high": 196.41,
            "current_stop": 182.16,
            "canonical_apply_eligible": False,
            "reasons": ["entry policy is not band_defined"],
        },
        {"in_entry_band": False, "below_stop": True, "ma_posture": "above 200d, below 20d and 50d"},
        "exception_owner_review",
        ["below_stop_or_invalidation"],
    )
    expect(candidate["candidate"] is False, f"below-stop row must not be a review candidate: {candidate}", errors)
    expect(candidate["recommended_entry_policy_action"] == "repair_or_reclaim_first", f"below-stop action should be repair first: {candidate}", errors)


def test_hygiene_uses_technical_refresh_when_surfaces_conflict(errors: list[str]) -> None:
    candidate = entry_policy_review_candidate(
        "AMZN",
        {
            "entry_policy": "underdefined",
            "coverage_lane": "watch",
            "workflow_state": "WATCH",
            "band_status": "IN_BAND",
            "current_band_low": 252.27,
            "current_band_high": 267.19,
            "current_stop": 244.81,
            "canonical_apply_eligible": False,
            "reasons": ["entry policy is not band_defined"],
        },
        {"in_entry_band": False, "below_stop": False, "ma_posture": "above 200d, below 20d and 50d"},
        "exception_owner_review",
        ["canonical_apply_eligible is not true"],
    )
    expect(candidate["candidate"] is False, f"conflicting band proposal must not create review candidate: {candidate}", errors)
    expect("technical_refresh_not_in_band_but_band_proposals_in_band" in candidate["surface_conflicts"], f"surface conflict should be explicit: {candidate}", errors)


def main() -> int:
    errors: list[str] = []
    test_watch_lane_in_band_surfaces_entry_policy_review(errors)
    test_below_stop_still_blocks_entry_policy_review(errors)
    test_hygiene_candidate_reuses_existing_surfaces(errors)
    test_hygiene_below_stop_is_repair_first(errors)
    test_hygiene_uses_technical_refresh_when_surfaces_conflict(errors)
    if errors:
        print("entry_policy_opportunity_surface_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("entry_policy_opportunity_surface_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
