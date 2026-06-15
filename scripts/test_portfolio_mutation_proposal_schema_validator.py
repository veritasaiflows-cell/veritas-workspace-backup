from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import portfolio_mutation_proposal_schema_validator as validator


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def common_packet(mutation_type: str) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "schema_version": 1,
        "generated_at_utc": "2026-05-11T00:00:00Z",
        "proposal_id": f"test-{mutation_type}-001",
        "mutation_type": mutation_type,
        "ticker_or_scope": "TEST",
        "current_state": {"state": "current"},
        "proposed_state": {"state": "proposed for review only"},
        "why_now": "Review packet for owner decision; no authority granted.",
        "evidence": ["source artifact reviewed"],
        "source_freshness": {"overall_classification": "current", "trust_level": "clean"},
        "base_case": "Base case for review.",
        "bear_case": "Bear case for review.",
        "risk_rule_check": {"status": "pass"},
        "concentration_check": {"status": "pass"},
        "technical_gate": {"status": "pass"},
        "catalyst_gate": {"status": "clear"},
        "owner_decision_required": True,
        "owner_approval_granted": False,
        "apply_allowed": False,
        "canonical_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "trade_or_account_action_allowed": False,
        "main_session_final_action_required": True,
        "proposed_files_to_edit": ["03. Portfolio/Portfolio Snapshot.md"],
        "rollback_or_reversal_note": "Discard packet if owner rejects.",
        "stop_lines_triggered": [],
    }
    if mutation_type in {"sleeve_change", "rebalance", "cash_target_change"}:
        packet.update({
            "current_portfolio_model": {"cash_target_pct": 10},
            "proposed_portfolio_model": {"cash_target_pct": 12},
            "current_cash_target_pct": 10,
            "proposed_cash_target_pct": 12,
            "sleeve_deltas": [],
            "sector_exposure_before_after": [],
            "correlated_sleeve_exposure_before_after": [],
            "risk_rule_check": {
                "status": "pass",
                "references": [
                    "25% sector cap",
                    "15% normal single-name ceiling",
                    "speculative sleeve cap",
                    "catalyst-window exception check",
                ],
            },
        })
    elif mutation_type == "ticker_lane_change":
        packet.update({
            "ticker": "GS",
            "current_lane_status_tuple": {"lane": "execution", "state": "ALMOST"},
            "proposed_lane_status_tuple": {"lane": "execution", "state": "promotion review"},
            "thesis_gate": {"status": "pass"},
            "macro_regime_gate": {"status": "pass"},
            "risk_sizing_gate": {"status": "warning"},
            "sector_correlation_artifact": {"status": "available_review_only", "path": "tmp/sector-correlation-check.json"},
            "owner_conflict_check": {"status": "pass", "conflicts": []},
            "promotion_review_queue": {"row_present": True},
        })
    elif mutation_type == "canonical_status_move":
        status_tuple = {
            "coverage_watchlist": "tracked",
            "execution_board": "almost deployable / constructive",
            "portfolio_snapshot": "tactical watch",
            "portfolio_config": "ALMOST",
        }
        packet.update({
            "current_status_tuple": copy.deepcopy(status_tuple),
            "proposed_status_tuple": copy.deepcopy(status_tuple),
            "affected_owner_surfaces": sorted(status_tuple),
            "field_level_deltas": [],
            "canonical_invariant_checks": {"status": "pass"},
        })
    return packet


def validate(packet: dict[str, Any]) -> dict[str, Any]:
    return validator.validate_packet(packet)


def test_valid_packets(errors: list[str]) -> None:
    for mutation_type in validator.ALLOWED_MUTATION_TYPES:
        result = validate(common_packet(mutation_type))
        expect(result["ok"] is True, f"valid {mutation_type} packet should pass: {result}", errors)


def test_authority_flags_fail_closed(errors: list[str]) -> None:
    cases = {
        "owner_decision_required": False,
        "owner_approval_granted": True,
        "apply_allowed": True,
        "portfolio_mutation_allowed": True,
    }
    for key, value in cases.items():
        packet = common_packet("ticker_lane_change")
        packet[key] = value
        result = validate(packet)
        expect(result["ok"] is False, f"authority flag {key}={value!r} should fail", errors)
        expect(any(key in blocker for blocker in result.get("blockers", [])), f"authority blocker should name {key}: {result}", errors)


def test_forbidden_language_and_surfaces_fail(errors: list[str]) -> None:
    packet = common_packet("ticker_lane_change")
    packet["why_now"] = "This is clear to deploy as an approved add."
    result = validate(packet)
    expect(result["ok"] is False, f"forbidden language should fail: {result}", errors)
    expect(any("forbidden" in blocker for blocker in result.get("blockers", [])), f"forbidden language blocker missing: {result}", errors)

    packet = common_packet("ticker_lane_change")
    packet["proposed_files_to_edit"] = ["brokerage/account-orders.json"]
    result = validate(packet)
    expect(result["ok"] is False, f"brokerage/account edit surface should fail: {result}", errors)
    expect(any("forbidden surface" in blocker for blocker in result.get("blockers", [])), f"forbidden surface blocker missing: {result}", errors)


def test_unknown_type_and_status_tuple_fail(errors: list[str]) -> None:
    packet = common_packet("ticker_lane_change")
    packet["mutation_type"] = "trade_order"
    result = validate(packet)
    expect(result["ok"] is False, "unknown mutation_type must fail", errors)

    packet = common_packet("canonical_status_move")
    del packet["current_status_tuple"]["portfolio_config"]
    result = validate(packet)
    expect(result["ok"] is False, "canonical status tuple missing an owner surface must fail", errors)
    expect(any("missing owner surfaces" in blocker for blocker in result.get("blockers", [])), f"missing owner surface blocker missing: {result}", errors)


def main() -> int:
    errors: list[str] = []
    test_valid_packets(errors)
    test_authority_flags_fail_closed(errors)
    test_forbidden_language_and_surfaces_fail(errors)
    test_unknown_type_and_status_tuple_fail(errors)
    if errors:
        print("portfolio_mutation_proposal_schema_validator_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("portfolio_mutation_proposal_schema_validator_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
