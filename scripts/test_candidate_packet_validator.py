from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import candidate_packet_validator


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def install_temp_sources(tmp: Path) -> None:
    write_json(
        tmp / "portfolio-config.json",
        {
            "tracked_universe": {
                "GS": {
                    "coverage_lane": "execution",
                    "sector": "Financials",
                    "workflow_state": "ALMOST",
                    "sizing_tier": "starter",
                }
            },
            "entry_bands": {"GS": {"low": 650, "high": 670, "stop": 610}},
        },
    )
    write_json(tmp / "deployment-check.json", {"records": [{"ticker": "GS", "action_state": "ALMOST DEPLOYABLE"}]})
    write_json(tmp / "earnings-calendar.json", {"records": [{"ticker": "GS", "next_earnings_date": "2026-07-15"}]})
    (tmp / "Promotion Review Queue.md").write_text("| Ticker | Status |\n| GS | Review |\n", encoding="utf-8")
    candidate_packet_validator.PORTFOLIO_CONFIG = tmp / "portfolio-config.json"
    candidate_packet_validator.DEPLOYMENT_CHECK = tmp / "deployment-check.json"
    candidate_packet_validator.EARNINGS_CALENDAR = tmp / "earnings-calendar.json"
    candidate_packet_validator.QUEUE_NOTE = tmp / "Promotion Review Queue.md"


def base_packet() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at_utc": "2026-05-10T00:00:00Z",
        "ticker": "GS",
        "proposed_lane": "execution",
        "source_surface": "portfolio config plus deployment check plus canonical notes",
        "thesis_evidence_source": "research coverage source",
        "canonical_trigger_source": "deployment trigger sheet",
        "canonical_portfolio_source": "portfolio snapshot",
        "thesis_exists": True,
        "levels_exist": True,
        "timing_posture": "clean",
        "portfolio_competition_assessed": True,
        "sector_cap_checked": True,
        "correlated_sleeve_checked": True,
        "regime_score_total": 17,
        "regime_score_rank": 5,
        "current_watch_state": "ALMOST",
        "current_trigger_state": "ALMOST DEPLOYABLE",
        "entry_band_defined": True,
        "invalidation_defined": True,
        "sizing_tier_defined": True,
        "catalyst_window_status": "clear",
        "sector": "Financials",
        "correlated_sleeve": "Financials peer context checked",
        "sector_cap_check": {"status": "pass", "source": "portfolio snapshot"},
        "five_gate_status": {
            "thesis_gate": "pass",
            "macro_and_regime_gate": "pass",
            "technical_gate": "pass",
            "catalyst_gate": "pass",
            "risk_and_sizing_gate": "pass",
        },
        "missing_gates": [],
        "promotion_blockers": [],
        "promotion_candidate": True,
        "promotion_review_required": True,
        "owner_conflict_check": {"status": "pass", "conflicts": []},
        "sector_correlation_artifact": {"status": "available_review_only", "path": "tmp/sector-correlation-check.json"},
        "current_canonical_status_tuple": {"watchlist": "ALMOST", "trigger": "ALMOST DEPLOYABLE"},
        "proposed_canonical_status_tuple": {"watchlist": "promotion review", "trigger": "promotion review"},
        "canonical_status_move_required": False,
        "notes": ["Review-only packet; owner review required before canonical changes."],
    }


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate(packet: dict[str, Any], trust_context: dict[str, Any] | None = None) -> dict[str, Any]:
    return candidate_packet_validator.validate_packet(packet, trust_context=trust_context)


def test_base_packet_passes(errors: list[str]) -> None:
    result = validate(base_packet())
    expect(result["ok"] is True, f"base packet should pass: {result}", errors)


def test_forbidden_authority_vocabulary_fails(errors: list[str]) -> None:
    forbidden_terms = [
        "buy",
        "add",
        "trim",
        "sell",
        "size",
        "sizing",
        "execute",
        "trade",
        "deployable now",
        "candidate weight",
        "target weight",
        "win probability",
        "deploy probability",
        "expected return",
        "green light",
        "clear to deploy",
        "tactical add",
        "disciplined size",
    ]
    for term in forbidden_terms:
        packet = base_packet()
        packet["notes"] = [f"Generated packet leaked forbidden phrase: {term}."]
        result = validate(packet)
        blockers = " | ".join(result.get("blockers", []))
        expect(result["ok"] is False, f"forbidden term {term!r} should fail validation", errors)
        expect("forbidden authority vocabulary" in blockers, f"forbidden term {term!r} should produce authority-vocabulary blocker: {result}", errors)


def test_promotion_candidate_requires_all_five_gates_pass(errors: list[str]) -> None:
    packet = base_packet()
    packet["five_gate_status"]["macro_and_regime_gate"] = "warning"
    packet["missing_gates"] = ["macro_and_regime_gate"]
    result = validate(packet)
    blockers = " | ".join(result.get("blockers", []))
    expect(result["ok"] is False, "promotion_candidate=true with a non-pass gate must fail", errors)
    expect("non-passing gates" in blockers, f"non-pass gate blocker should be explicit: {result}", errors)


def test_missing_sector_and_correlation_checks_fail_closed(errors: list[str]) -> None:
    packet = base_packet()
    packet["sector_cap_checked"] = False
    packet["correlated_sleeve_checked"] = False
    result = validate(packet)
    blockers = " | ".join(result.get("blockers", []))
    expect(result["ok"] is False, "missing sector/correlation checks must fail closed", errors)
    expect("sector cap check was not performed" in blockers, f"sector blocker missing: {result}", errors)
    expect("correlated sleeve check was not performed" in blockers, f"correlation blocker missing: {result}", errors)


def test_system_trust_gate_blocks_candidate_readiness(errors: list[str]) -> None:
    trust_context = {
        "source_freshness": {
            "overall_classification": "partial",
            "trust_level": "review_required",
            "presentation_allowed": False,
            "capital_action_allowed": False,
        }
    }
    result = validate(base_packet(), trust_context=trust_context)
    blockers = " | ".join(result.get("blockers", []))
    expect(result["ok"] is False, "degraded system trust context must block promotion_candidate=true", errors)
    expect("system trust gate degraded" in blockers, f"trust-gate blocker should be explicit: {result}", errors)


def test_owner_conflict_and_sector_artifact_required(errors: list[str]) -> None:
    packet = base_packet()
    packet["owner_conflict_check"] = {"status": "failed", "conflicts": ["Execution Board disagrees with portfolio-config"]}
    packet["sector_correlation_artifact"] = {"status": "missing", "path": ""}
    result = validate(packet)
    blockers = " | ".join(result.get("blockers", []))
    expect(result["ok"] is False, "owner conflict / missing sector artifact must fail closed", errors)
    expect("owner_conflict_check is not pass" in blockers, f"owner conflict status blocker missing: {result}", errors)
    expect("owner_conflict_check contains conflicts" in blockers, f"owner conflict detail blocker missing: {result}", errors)
    expect("sector_correlation_artifact" in blockers, f"sector correlation blocker missing: {result}", errors)


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        install_temp_sources(Path(tmpdir))
        test_base_packet_passes(errors)
        test_forbidden_authority_vocabulary_fails(errors)
        test_promotion_candidate_requires_all_five_gates_pass(errors)
        test_missing_sector_and_correlation_checks_fail_closed(errors)
        test_system_trust_gate_blocks_candidate_readiness(errors)
        test_owner_conflict_and_sector_artifact_required(errors)
    if errors:
        print("candidate_packet_validator_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("candidate_packet_validator_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
