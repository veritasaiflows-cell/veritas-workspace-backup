from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import current_regime_analog_matcher as matcher


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def event(event_id: str, label: str, shocks: list[str], small_60d: float | None = 1.0) -> dict:
    return {
        "event_id": event_id,
        "label": label,
        "start": "2020-01-01",
        "end": "2020-02-01",
        "shock_types": shocks,
        "setup": "fixture setup",
        "analog_notes": "fixture analog",
        "outcomes": {
            "large_cap": {"event_window_return_pct": -1, "forward_returns_pct": {"60d": 2, "252d": 8}},
            "small_cap": {"event_window_return_pct": -2, "forward_returns_pct": {"60d": small_60d, "252d": 9}},
        },
        "small_vs_large": {
            "status": "ok" if small_60d is not None else "unavailable",
            "event_window_small_minus_large_pct": -1 if small_60d is not None else None,
            "forward_small_minus_large_pct": {"20d": 0.1, "60d": small_60d, "120d": 0.3, "252d": 1.0} if small_60d is not None else {},
        },
    }


def sample_historical() -> dict:
    return {
        "status": "ok",
        "current_context": {"current_analog_tags": ["rate_stabilization", "breadth_repair"]},
        "events": [
            event("soft", "Soft landing", ["rate_stabilization", "breadth_repair"], small_60d=-2),
            event("rate", "Rate shock", ["rate_shock", "policy_tightening"], small_60d=3),
            event("credit", "Credit stress", ["credit_stress", "liquidity_shock"], small_60d=-5),
            event("war", "War shock", ["war", "oil_shock"], small_60d=None),
        ],
    }


def sample_wf61() -> dict:
    return {
        "status": "ok",
        "market_data_as_of": "2026-06-12",
        "summary": {
            "bucket_summary": {
                "small_cap": {"improving": ["IWM"]},
                "mid_cap": {"improving": ["IJH"]},
            }
        },
    }


def test_build_payload_contract(errors: list[str]) -> None:
    payload = matcher.build_payload(sample_historical(), sample_wf61())
    expect(payload["status"] == "ok", f"payload should validate ok: {payload.get('validation')}", errors)
    expect(payload["authority"]["calibrated_probability_allowed"] is False, "probability authority must remain false", errors)
    expect(payload["authority"]["scoring_model_allowed"] is False, "scoring authority must remain false", errors)
    panel = payload["scenario_context_panel"]
    fits = {row["fit"] for row in panel["primary_analogs"]}
    expect("direct_current_theme" in fits, "direct current theme analog missing", errors)
    expect("rate_shock_precedent" in fits, "rate shock precedent analog missing", errors)
    stress_fits = {row["fit"] for row in panel["stress_caution_analogs"]}
    expect("stress_caution" in stress_fits, "stress caution analog missing", errors)
    expect("inflation_geopolitical_caution" in stress_fits, "inflation/geopolitical caution analog missing", errors)


def test_forbidden_language_absent(errors: list[str]) -> None:
    payload = matcher.build_payload(sample_historical(), sample_wf61())
    text = json.dumps(payload, sort_keys=True).lower()
    for phrase in ("win probability", "expected return", "model-ranked", "% chance", "trade approval"):
        expect(phrase not in text, f"forbidden phrase present: {phrase}", errors)


def main() -> int:
    errors: list[str] = []
    test_build_payload_contract(errors)
    test_forbidden_language_absent(errors)
    if errors:
        print("current_regime_analog_matcher_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("current_regime_analog_matcher_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
