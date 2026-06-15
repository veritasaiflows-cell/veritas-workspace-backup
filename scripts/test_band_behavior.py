from __future__ import annotations

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "scripts"))

from band_behavior import band_behavior_by_ticker, band_behavior_for_record, format_band_behavior, qualified_band_behavior  # noqa: E402


def etn_fixture() -> tuple[dict, dict]:
    record = {
        "ticker": "ETN",
        "action_state": "DEPLOYABLE NOW",
        "close": 419.0,
        "entry_band": {"low": 395.59, "high": 420.31, "label": "395.59-420.31"},
    }
    market_state = {
        "data": {
            "actionable": {
                "ETN": {
                    "open": 402.04,
                    "day_low": 396.44,
                    "day_high": 420.88,
                    "last_price": 419.0,
                }
            }
        }
    }
    return record, market_state


def main() -> int:
    errors: list[str] = []
    record, market_state = etn_fixture()

    behavior = band_behavior_for_record(record, market_state)
    expected_flags = {
        "lower_band_tested_and_reclaimed",
        "closed_near_upper_band",
        "intraday_above_band",
        "closed_in_band",
        "no_chase_active",
    }
    missing = expected_flags - set(behavior.get("flags", []))
    if missing:
        errors.append(f"missing ETN flags: {sorted(missing)} from {behavior.get('flags')}")
    if not behavior.get("available"):
        errors.append("expected ETN behavior to be available")
    if behavior.get("distance_low_to_band_low") != 0.85:
        errors.append(f"expected low-to-band distance 0.85, got {behavior.get('distance_low_to_band_low')}")
    if behavior.get("distance_close_to_band_high") != 1.31:
        errors.append(f"expected close-to-ceiling distance 1.31, got {behavior.get('distance_close_to_band_high')}")
    formatted = format_band_behavior(behavior)
    if "tested lower-band support and reclaimed" not in formatted or "no-chase active" not in formatted:
        errors.append(f"formatted summary missed expected language: {formatted}")

    trigger = {"records": [record, {"ticker": "LMT", "action_state": "DO NOT TOUCH", "close": 512.25}]}
    qualified = qualified_band_behavior(trigger, market_state)
    if [item.get("ticker") for item in qualified] != ["ETN"]:
        errors.append(f"expected only actionable ETN qualified behavior, got {qualified}")
    by_ticker = band_behavior_by_ticker(trigger, market_state)
    if sorted(by_ticker) != ["ETN"]:
        errors.append(f"expected by-ticker ETN only, got {sorted(by_ticker)}")

    missing_behavior = band_behavior_for_record({"ticker": "BAD", "action_state": "DEPLOYABLE NOW"}, market_state)
    if missing_behavior.get("available"):
        errors.append("expected missing band/close behavior to be unavailable")

    if errors:
        print("band behavior test failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("band behavior test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
