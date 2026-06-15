from __future__ import annotations

import copy
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import sec_evidence_packet_validator as mod


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def sample_packet() -> dict:
    authority = {
        "review_packet_generation_allowed": True,
        "official_source_evidence_allowed": True,
        "canonical_mutation_allowed_by_this_packet": False,
        "portfolio_mutation_allowed_by_this_packet": False,
        "proposal_apply_allowed": False,
        "owner_approval_granted": False,
        "owner_approval_inference_allowed": False,
        "trade_execution_allowed": False,
        "trade_or_account_action_allowed": False,
        "brokerage_account_action_allowed": False,
        "money_movement_allowed": False,
        "sizing_allocation_action_allowed": False,
        "model_ranked_deployment_allowed": False,
    }
    return {
        "schema_version": 1,
        "generated_at_utc": "2026-05-17T00:00:00Z",
        "status": "ok",
        "evidence_class": "official_sec_edgar",
        "sec_user_agent": "Veritas OpenClaw Research veritasaiflows@gmail.com",
        "authority": authority,
        "packets": [
            {
                "ticker": "GOOG",
                "status": "ok",
                "company_name": "Alphabet Inc.",
                "cik": "0001652044",
                "evidence_class": "official_sec_edgar",
                "retrievals": {"filings": {"10-K": {}, "10-Q": {}, "8-K": {}}},
                "provenance": {"retrieved_at_utc": "2026-05-17T00:00:00Z", "sec_skill_sha256": "abc"},
                "authority": authority,
            }
        ],
    }


def test_valid_passes(errors: list[str]) -> None:
    report = mod.validate_packet(sample_packet())
    expect(report["summary"]["critical"] == 0, f"valid packet should have 0 critical: {report}", errors)


def test_authority_leak_fails(errors: list[str]) -> None:
    data = sample_packet()
    data["authority"]["trade_execution_allowed"] = True
    report = mod.validate_packet(data)
    expect(any(item.get("issue") == "authority_field_not_false" for item in report["findings"]), "authority leak should fail", errors)


def test_bad_user_agent_fails(errors: list[str]) -> None:
    data = sample_packet()
    data["sec_user_agent"] = "SEC-AI-Research-Agent admin@example.com"
    report = mod.validate_packet(data)
    expect(any(item.get("issue") == "invalid_sec_user_agent" for item in report["findings"]), "placeholder SEC user agent should fail", errors)


def test_forbidden_language_fails(errors: list[str]) -> None:
    data = sample_packet()
    data["packets"][0]["note"] = "This has a 60% chance and win probability."
    report = mod.validate_packet(data)
    expect(any(item.get("issue") == "forbidden_probability_or_execution_language" for item in report["findings"]), "forbidden language should fail", errors)


def main() -> int:
    errors: list[str] = []
    test_valid_passes(errors)
    test_authority_leak_fails(errors)
    test_bad_user_agent_fails(errors)
    test_forbidden_language_fails(errors)
    if errors:
        print("sec_evidence_packet_validator_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("sec_evidence_packet_validator_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
