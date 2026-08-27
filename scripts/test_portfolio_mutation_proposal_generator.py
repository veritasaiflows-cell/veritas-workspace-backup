from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_proposal_generator as generator
import portfolio_mutation_proposal_schema_validator as schema_validator


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def sample_rec() -> dict[str, Any]:
    return {
        "ticker": "ETN",
        "current_state": "DEPLOYABLE NOW",
        "entry_band_status": "IN_BAND",
        "recommended_action": "deploy_candidate",
        "recommendation_action": "deploy",
        "macro_regime_check": "supportive",
        "thesis": "Electrification setup remains intact.",
        "base_case": "Base case: setup remains review-worthy inside written band.",
        "bear_case": "Bear case: defer if invalidation fails or macro fit worsens.",
        "sizing_risk_envelope": {
            "review_boundary": "Owner-gated risk envelope only; no portfolio mutation or account-action authority.",
            "risk_thresholds": {"max_single_position_normal_pct": 15, "max_sector_pct": 25},
        },
        "sector_context": {"status": "available_review_only"},
        "blocked_reasons": [],
    }


def test_generated_payload_authority(errors: list[str]) -> None:
    daily_path = generator.TMP / "daily-review-objects-post-close.json"
    # Avoid touching live artifacts here; directly exercise the shared authority contract.
    authority = generator.TOP_LEVEL_AUTHORITY
    expect(authority["gated_portfolio_note_model_mutation_allowed"] is True, "top-level posture should allow gated portfolio note/model mutation", errors)
    expect(authority.get("owner_approval_granted_for_portfolio_note_model_mutation_class") is not True, "bundle must not encode owner approval as granted", errors)
    expect(authority["proposal_apply_allowed"] is False, "recommendation bundle must not be self-applying", errors)
    expect(authority["per_packet_owner_approval_inferred"] is False, "bundle must not infer per-packet approval", errors)
    expect(authority["trade_or_account_action_allowed"] is False, "trade/account authority must remain blocked", errors)
    expect(authority["trade_execution_allowed"] is False, "trade execution must remain blocked", errors)
    expect(daily_path.name == "daily-review-objects-post-close.json", "sanity check path naming", errors)


def test_generated_packet_validates(errors: list[str]) -> None:
    daily = {
        "source_freshness": {"overall_classification": "current", "trust_level": "clean"},
    }
    config = {"portfolio": {"cash": 10}}
    packet = generator.proposal_for(
        sample_rec(),
        window="post-close",
        generated_at="2026-05-11T00:00:00Z",
        daily=daily,
        config=config,
        config_meta={"workflow_state": "DEPLOYED", "coverage_lane": "execution", "entry_policy": "band_defined"},
        band_proposal={"band_status": "IN_BAND", "distance_to_band_pct": 0.0, "days_to_earnings": 85, "earnings_state": "CLEAR"},
        deployment_record={"action_state": "DEPLOYABLE NOW", "close": 419.0, "in_entry_band": True, "below_stop": False},
    )
    result = schema_validator.validate_packet(packet)
    expect(result["ok"] is True, f"generated packet should satisfy schema validator: {result}", errors)
    expect(packet["portfolio_mutation_allowed"] is False, "portfolio mutation flag must be false", errors)
    expect(packet["owner_approval_granted"] is False, "owner approval flag must be false", errors)
    expect(packet["proposed_state"]["state_change_requested"] is False, "packet must not request direct state change", errors)


def test_forbidden_text_sanitized(errors: list[str]) -> None:
    text = generator.clean_text("owner-approved buy trade execute sell trim approval granted")
    lowered = text.lower()
    for forbidden in ("owner-approved", "buy", "trade", "execute", "sell", "trim", "approval granted"):
        expect(forbidden not in lowered, f"forbidden text should be sanitized: {forbidden} -> {text}", errors)


def test_reclaim_stop_label_preserved(errors: list[str]) -> None:
    rec = sample_rec()
    rec["entry_band_status"] = "BELOW_RECLAIM_STOP"
    rec["band_status_note"] = "Band proposal is below a proposed reclaim/vault stop; authoritative deployment below_stop is false."
    packet = generator.proposal_for(
        rec,
        window="post-close",
        generated_at="2026-05-11T00:00:00Z",
        daily={"source_freshness": {"overall_classification": "current", "trust_level": "clean"}},
        config={"portfolio": {"cash": 10}},
        config_meta={"workflow_state": "WATCH", "coverage_lane": "watch", "entry_policy": "band_defined"},
        band_proposal={"band_status": "BELOW_STOP", "distance_to_band_pct": -6.5, "days_to_earnings": 85, "earnings_state": "CLEAR"},
        deployment_record={"action_state": "ALMOST DEPLOYABLE", "close": 421.92, "in_entry_band": False, "below_stop": False},
    )
    expect(packet["technical_gate"]["entry_band_status"] == "BELOW_RECLAIM_STOP", f"technical gate should use normalized reclaim label: {packet['technical_gate']}", errors)
    expect(packet["technical_gate"]["raw_band_status"] == "BELOW_STOP", "raw proposal label should remain auditable", errors)
    expect(packet["technical_gate"]["below_stop"] is False, "deployment below_stop should remain false", errors)


def test_current_stop_flows_to_technical_gate(errors: list[str]) -> None:
    packet = generator.proposal_for(
        sample_rec(),
        window="post-close",
        generated_at="2026-05-11T00:00:00Z",
        daily={"source_freshness": {"overall_classification": "current", "trust_level": "clean"}},
        config={"portfolio": {"cash": 10}},
        config_meta={"workflow_state": "WATCH", "coverage_lane": "watch", "entry_policy": "band_defined"},
        band_proposal={
            "band_status": "IN_BAND",
            "current_band_low": 354.25,
            "current_band_high": 369.69,
            "current_stop": 341.07,
        },
        deployment_record={"action_state": "ALMOST DEPLOYABLE", "close": 349.82, "in_entry_band": False, "below_stop": False},
    )
    expect(packet["technical_gate"]["stop_or_invalidation"] == 341.07, f"technical gate should preserve current_stop fallback: {packet['technical_gate']}", errors)


def test_canonical_eligible_suggested_band_flows_to_technical_gate(errors: list[str]) -> None:
    packet = generator.proposal_for(
        sample_rec(),
        window="post-close",
        generated_at="2026-05-11T00:00:00Z",
        daily={"source_freshness": {"overall_classification": "current", "trust_level": "clean"}},
        config={"portfolio": {"cash": 10}},
        config_meta={"workflow_state": "WATCH", "coverage_lane": "watch", "entry_policy": "band_defined"},
        band_proposal={
            "band_status": "IN_BAND",
            "distance_to_band_pct": -2.9,
            "current_band_low": 202.81,
            "current_band_high": 212.23,
            "current_stop": 192.95,
            "suggested_band_low": 185.14,
            "suggested_band_high": 205.25,
            "suggested_stop": 176.01,
            "canonical_apply_eligible": True,
        },
        deployment_record={"action_state": "ALMOST DEPLOYABLE", "close": 196.06, "in_entry_band": True, "below_stop": False},
    )
    technical = packet["technical_gate"]
    expect(technical["current_band_low"] == 185.14, f"technical gate should use SQL-first suggested low: {technical}", errors)
    expect(technical["current_band_high"] == 205.25, f"technical gate should use SQL-first suggested high: {technical}", errors)
    expect(technical["stop_or_invalidation"] == 176.01, f"technical gate should use SQL-first suggested stop: {technical}", errors)
    expect(technical["band_source"] == "sql_first_band_proposal", f"technical gate should label SQL-first source: {technical}", errors)
    expect(technical["raw_band_proposal"]["current_band_low"] == 202.81, f"technical gate should preserve legacy band audit context: {technical}", errors)


def main() -> int:
    errors: list[str] = []
    test_generated_payload_authority(errors)
    test_generated_packet_validates(errors)
    test_forbidden_text_sanitized(errors)
    test_reclaim_stop_label_preserved(errors)
    test_current_stop_flows_to_technical_gate(errors)
    test_canonical_eligible_suggested_band_flows_to_technical_gate(errors)
    if errors:
        print("portfolio_mutation_proposal_generator_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("portfolio_mutation_proposal_generator_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
