from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import daily_price_trend_signals as trend

WORKSPACE = SCRIPTS_DIR.parent


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def assert_authority(obj: dict[str, Any], label: str, errors: list[str]) -> None:
    for key, expected in trend.AUTHORITY_FLAGS.items():
        expect(obj.get(key) == expected, f"{label} authority mismatch for {key}", errors)


def all_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for key, child in value.items():
            out.extend(all_strings(key))
            out.extend(all_strings(child))
        return out
    if isinstance(value, list):
        out: list[str] = []
        for child in value:
            out.extend(all_strings(child))
        return out
    return []


def test_fixture_signal_boundaries(errors: list[str]) -> None:
    signal = trend.build_signal(
        "GS",
        {
            "ticker": "GS",
            "close": 936.48,
            "ma_posture": "above all MAs -- bullish 20>50>200 stack",
            "above_ma20": True,
            "above_ma50": True,
            "above_ma200": True,
            "in_entry_band": False,
            "below_stop": False,
            "data_date": "2026-05-08",
        },
        {
            "ticker": "GS",
            "band_status": "NEAR_BAND",
            "trend_stack": "BULLISH_STACK",
            "days_to_earnings": 65,
            "needs_review": False,
        },
        {
            "ticker": "GS",
            "surface_state": "ALMOST DEPLOYABLE",
            "source_group": "ALMOST DEPLOYABLE",
            "band_position": "1.0% above band top",
            "macro_gate": "DEGRADED",
            "why": "workflow state is ALMOST -- constructive but not yet promoted",
        },
        {"ticker": "GS", "total": 17, "thesis_status": "intact but secondary to JPM for primary bank exposure"},
        "missing",
        trust_degraded=True,
    )
    assert_authority(signal, "fixture signal", errors)
    expect(signal.get("trend_signal") in trend.DIRECTIONAL_LABELS, "trend signal should use allowed vocabulary", errors)
    expect(signal.get("promotion_readiness_direction") in trend.DIRECTION_LABELS, "readiness direction should use allowed vocabulary", errors)
    for value in (signal.get("deltas") or {}).values():
        expect(value in trend.DIRECTION_LABELS, f"delta uses disallowed vocabulary: {value}", errors)
    expect(signal.get("promotion_readiness_direction") == "unchanged", "degraded macro/system trust gate should cap readiness direction", errors)
    expect(signal.get("current_state", {}).get("macro_capped") is True, "degraded macro gate should be visible as macro_capped", errors)
    expect(signal.get("prior_state", {}).get("source") == "none", "missing history should not invent prior-state source", errors)
    expect(all(value == "unknown" for value in (signal.get("deltas") or {}).values()), "missing history should leave deltas unknown", errors)


def test_below_stop_fails_closed(errors: list[str]) -> None:
    signal = trend.build_signal(
        "MSFT",
        {"ticker": "MSFT", "close": 470.0, "below_stop": False, "in_entry_band": False},
        {"ticker": "MSFT", "band_status": "BELOW_STOP"},
        {"ticker": "MSFT", "surface_state": "ALMOST DEPLOYABLE", "source_group": "ALMOST DEPLOYABLE"},
        {},
        "missing",
    )
    expect(signal.get("trend_signal") == "blocked", "BELOW_STOP band status should block the trend signal", errors)
    expect(signal.get("promotion_readiness_direction") == "blocked", "BELOW_STOP band status should block readiness direction", errors)
    expect("below_stop" in (signal.get("blockers") or []), "BELOW_STOP band status should add below_stop blocker", errors)


def test_deployable_now_does_not_emit_promotion_increase(errors: list[str]) -> None:
    signal = trend.build_signal(
        "ETN",
        {"ticker": "ETN", "close": 401.51, "below_stop": False, "in_entry_band": True},
        {"ticker": "ETN", "band_status": "IN_BAND"},
        {"ticker": "ETN", "surface_state": "DEPLOYABLE NOW", "source_group": "DEPLOYABLE NOW"},
        {},
        "partial",
    )
    expect(signal.get("trend_signal") == "stable", "owner-promoted/deployable names should not be top-improving promotion candidates", errors)
    expect(signal.get("promotion_readiness_direction") == "unchanged", "owner-promoted/deployable names should not show increased promotion readiness", errors)


def test_below_band_does_not_emit_improving_promotion_signal(errors: list[str]) -> None:
    signal = trend.build_signal(
        "JPM",
        {"ticker": "JPM", "close": 302.10, "below_stop": False, "in_entry_band": False},
        {"ticker": "JPM", "band_status": "OUTSIDE_BAND"},
        {"ticker": "JPM", "surface_state": "ALMOST DEPLOYABLE", "source_group": "ALMOST DEPLOYABLE", "band_position": "1.5% below band low"},
        {},
        "partial",
    )
    expect(signal.get("trend_signal") == "weakening", "below-band/reclaim-only setups should not be improving promotion candidates", errors)
    expect(signal.get("promotion_readiness_direction") == "decreased", "below-band/reclaim-only setups should decrease promotion readiness", errors)


def test_material_shortlist_includes_gs(errors: list[str]) -> None:
    readiness = {
        "groups": {
            "PROMOTION REVIEW": [{"ticker": "ETN", "surface_state": "PROMOTION REVIEW", "why": "in band"}],
            "ALMOST DEPLOYABLE": [
                {
                    "ticker": "GS",
                    "surface_state": "ALMOST DEPLOYABLE",
                    "why": "workflow state is ALMOST -- constructive but not yet promoted",
                    "trigger": "tactical add only while JPM remains primary bank setup",
                }
            ],
        }
    }
    signals = {
        "GS": {
            "ticker": "GS",
            "trend_signal": "improving",
            "promotion_readiness_direction": "increased",
            "current_state": {"band_status": "NEAR_BAND"},
        }
    }
    shortlist = trend.material_shortlist(readiness, signals)
    tickers = {item.get("ticker") for item in shortlist}
    expect("GS" in tickers, "GS-style almost-deployable names must remain visible in shortlist", errors)
    expect("ETN" in tickers, "promotion-review names must remain visible in shortlist", errors)
    for item in shortlist:
        assert_authority(item, f"shortlist {item.get('ticker')}", errors)
        text = " ".join(trend.walk_strings(item)).lower()
        expect("tactical add" not in text, "shortlist context must not copy tactical add language", errors)
        expect("disciplined size" not in text, "shortlist context must not copy disciplined size language", errors)
        expect("sizing" not in text, "shortlist context must not emit sizing language", errors)


def test_live_payload_contract(errors: list[str]) -> None:
    try:
        payload = trend.build_payload("post-close")
    except FileNotFoundError:
        return
    assert_authority(payload, "payload", errors)
    expect(payload.get("consumer_posture") == "review_only", "payload should be review_only", errors)
    expect(payload.get("history_status") in {"missing", "partial", "available", "stale"}, "history_status should be honest bounded vocabulary", errors)
    expect(payload.get("canonical_mutation_allowed") is False, "payload must not allow canonical mutation", errors)
    expect(payload.get("portfolio_mutation_allowed") is False, "payload must not allow portfolio mutation", errors)
    expect(payload.get("deployment_state_mutation_allowed") is False, "payload must not allow deployment mutation", errors)
    expect(payload.get("trade_execution_allowed") is False, "payload must not allow trade execution", errors)
    expect(payload.get("owner_approval_required") is True, "payload must require owner approval", errors)
    expect(payload.get("owner_approval_granted") is False, "payload must not infer approval", errors)
    signals = payload.get("signals") or []
    expect(bool(signals), "live payload should emit signals when source artifacts exist", errors)
    for signal in signals:
        assert_authority(signal, f"signal {signal.get('ticker')}", errors)
        expect(signal.get("trend_signal") in trend.DIRECTIONAL_LABELS, f"bad trend label for {signal.get('ticker')}", errors)
        expect(signal.get("promotion_readiness_direction") in trend.DIRECTION_LABELS, f"bad direction label for {signal.get('ticker')}", errors)
        for value in (signal.get("deltas") or {}).values():
            expect(value in trend.DIRECTION_LABELS, f"bad delta label for {signal.get('ticker')}: {value}", errors)
    shortlist = payload.get("material_shortlist") or []
    shortlist_tickers = {item.get("ticker") for item in shortlist}
    expect("GS" in shortlist_tickers, "live payload should preserve GS material shortlist visibility when source artifact includes GS", errors)
    readiness = trend.load_json(trend.READINESS_PATH)
    promotion_review_records = ((readiness.get("groups") or {}).get("PROMOTION REVIEW") or [])
    if promotion_review_records:
        expect(any(item.get("source_group") == "PROMOTION REVIEW" for item in shortlist), "live payload should include PROMOTION REVIEW shortlist names when source group is non-empty", errors)
    expect(any(item.get("source_group") == "ALMOST DEPLOYABLE" for item in shortlist), "live payload should include ALMOST DEPLOYABLE shortlist names", errors)
    forbidden_blob = "\n".join(all_strings(payload)).lower()
    for forbidden in trend.FORBIDDEN_TEXT:
        expect(forbidden not in forbidden_blob, f"forbidden vocabulary present: {forbidden}", errors)


def test_written_artifact_if_present(errors: list[str]) -> None:
    path = WORKSPACE / "tmp" / "daily-price-trend-signals.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    assert_authority(data, "written artifact", errors)
    expect(data.get("canonical_mutation_allowed") is False, "written artifact must not allow canonical mutation", errors)


def main() -> int:
    errors: list[str] = []
    test_fixture_signal_boundaries(errors)
    test_below_stop_fails_closed(errors)
    test_deployable_now_does_not_emit_promotion_increase(errors)
    test_below_band_does_not_emit_improving_promotion_signal(errors)
    test_material_shortlist_includes_gs(errors)
    test_live_payload_contract(errors)
    test_written_artifact_if_present(errors)
    if errors:
        print("daily_price_trend_signals_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("daily_price_trend_signals_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
