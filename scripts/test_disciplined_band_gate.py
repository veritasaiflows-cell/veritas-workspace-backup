from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import disciplined_band_gate as gate
from daily_review_objects import capital_recommendations


AMD_BAND = {
    "disciplined_band_low": 295.33,
    "disciplined_band_high": 342.53,
    "disciplined_stop": 271.73,
    "band_state": "BACKFILLED",
    "disciplined_levels_set_at": "2026-05-06",
}
NEEDS_OWNER = {"band_state": "NEEDS_OWNER_BAND", "disciplined_band_low": None, "disciplined_band_high": None}


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_extension_auto_drop_when_extended(errors: list[str]) -> None:
    ext = gate.extension_assessment(485.75, AMD_BAND, atr14=31.11)
    expect(ext["auto_drop"] is True, "price 41.8% above disciplined high should auto-drop", errors)
    expect(ext["verdict"] == "EXTENDED_ABOVE_DISCIPLINED_BAND", "extended verdict expected", errors)
    expect(ext["atr_secondary_flag"] is True, "ATR distance should raise the secondary informational flag", errors)


def test_extension_within_band_does_not_drop(errors: list[str]) -> None:
    ext = gate.extension_assessment(310.0, AMD_BAND, atr14=31.11)
    expect(ext["auto_drop"] is False, "price inside the disciplined band must not auto-drop", errors)
    expect(ext["verdict"] == "WITHIN_OR_BELOW_DISCIPLINED_BAND", "in-band verdict expected", errors)


def test_extension_above_band_within_threshold(errors: list[str]) -> None:
    # ~2% above the 342.53 ceiling => above band but inside the 8% no-chase threshold.
    ext = gate.extension_assessment(349.0, AMD_BAND, atr14=31.11)
    expect(ext["auto_drop"] is False, "small overshoot within threshold must not auto-drop", errors)
    expect(ext["verdict"] == "ABOVE_BAND_WITHIN_THRESHOLD", "within-threshold verdict expected", errors)


def test_extension_no_band_never_drops(errors: list[str]) -> None:
    ext = gate.extension_assessment(999.0, NEEDS_OWNER, atr14=10.0)
    expect(ext["applies"] is False, "no owner-set band should not apply the gate", errors)
    expect(ext["auto_drop"] is False, "no owner-set band must never auto-drop (no silent guessing)", errors)
    expect(ext["verdict"] == "NO_DISCIPLINED_BAND", "no-band verdict expected", errors)


def test_extension_no_price(errors: list[str]) -> None:
    ext = gate.extension_assessment(None, AMD_BAND, atr14=31.11)
    expect(ext["applies"] is False, "missing price should not apply the gate", errors)
    expect(ext["auto_drop"] is False, "missing price must not auto-drop", errors)


def test_staleness_age_or_distance(errors: list[str]) -> None:
    # Old band (2026-05-06) as of a same-day date should be fresh on age; far price trips distance.
    fresh = gate.staleness_assessment(AMD_BAND, price=318.93, atr14=31.11, as_of=date(2026, 5, 10))
    expect(fresh["stale"] is False, "recent band at midpoint should be fresh", errors)

    aged = gate.staleness_assessment(AMD_BAND, price=318.93, atr14=31.11, as_of=date(2026, 8, 18))
    expect(aged["stale"] is True, "band older than 30 days should be stale (age arm)", errors)

    far = gate.staleness_assessment(AMD_BAND, price=485.75, atr14=31.11, as_of=date(2026, 5, 10))
    expect(far["stale"] is True, "price >2 ATR from midpoint should be stale (distance arm)", errors)
    expect(len(far["stale_reasons"]) >= 1, "distance staleness should record a reason", errors)


def test_staleness_no_band(errors: list[str]) -> None:
    st = gate.staleness_assessment(NEEDS_OWNER, price=100.0, atr14=5.0)
    expect(st["applies"] is False, "no owner-set band should not raise staleness", errors)
    expect(st["stale"] is False, "no owner-set band must not be flagged stale", errors)


def _clean_system() -> dict:
    return {"trust_level": "clean", "stop_line": False, "critical": 0, "trust_ceiling_reasons": []}


def _candidate(ticker: str) -> dict:
    return {
        "object_type": "ticker",
        "ticker": ticker,
        "category": "near_deployable",
        "recommendation_class": "review_for_possible_add",
        "band_status": "IN_BAND",
        "signal_score": 80,
        "recommended_next_step": "owner review",
    }


def test_override_flips_extended_deploy_candidate(errors: list[str]) -> None:
    bp = {"proposals": [{"ticker": "AMD", "close": 485.75, "atr14": 31.11}]}
    recs, _ = capital_recommendations([_candidate("AMD")], _clean_system(), band_proposals=bp)
    amd = recs[0]
    expect(
        amd["recommended_action"] == "extended_no_disciplined_entry",
        "extended deploy_candidate must be auto-dropped to watch",
        errors,
    )
    expect(amd["recommendation_action"] == "wait", "auto-dropped name should map to the wait family", errors)
    expect(amd["disciplined_extension_gate"]["auto_drop"] is True, "override should carry the extension gate", errors)


def test_override_keeps_in_band_deploy_candidate(errors: list[str]) -> None:
    bp = {"proposals": [{"ticker": "AMD", "close": 310.0, "atr14": 31.11}]}
    recs, _ = capital_recommendations([_candidate("AMD")], _clean_system(), band_proposals=bp)
    amd = recs[0]
    expect(
        amd["recommended_action"] == "deploy_candidate",
        "in-band candidate must stay a deploy_candidate",
        errors,
    )
    expect(amd["disciplined_extension_gate"]["auto_drop"] is False, "in-band candidate should not auto-drop", errors)


def test_staleness_payload_authority_and_delivery(errors: list[str]) -> None:
    bands = {"AMD": dict(AMD_BAND, ticker="AMD", authority_class="canonical_written_band_review_only_no_deployment_authority")}
    prop = {"AMD": {"ticker": "AMD", "close": 485.75, "atr14": 31.11}}
    payload = gate.build_staleness_alert_payload(bands, prop, as_of=date(2026, 8, 18), window="morning")
    expect(payload["consumer_posture"] == "review_only", "staleness payload must be review_only", errors)
    expect(
        payload["delivery"]["telegram_wiring"] == "not_wired_requires_owner_approval",
        "telegram delivery must remain unwired pending owner approval",
        errors,
    )
    expect(payload["authority"]["owner_approval_inferred"] is False, "no owner approval may be inferred", errors)
    expect("AMD" in payload["summary"]["extended_auto_drop_tickers"], "AMD should be listed as extended auto-drop", errors)
    expect("AMD" in payload["summary"]["stale_tickers"], "AMD should be listed as stale", errors)


def main() -> int:
    errors: list[str] = []
    test_extension_auto_drop_when_extended(errors)
    test_extension_within_band_does_not_drop(errors)
    test_extension_above_band_within_threshold(errors)
    test_extension_no_band_never_drops(errors)
    test_extension_no_price(errors)
    test_staleness_age_or_distance(errors)
    test_staleness_no_band(errors)
    test_override_flips_extended_deploy_candidate(errors)
    test_override_keeps_in_band_deploy_candidate(errors)
    test_staleness_payload_authority_and_delivery(errors)
    if errors:
        print("disciplined_band_gate_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("disciplined_band_gate_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
