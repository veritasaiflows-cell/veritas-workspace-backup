from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import authority_vocabulary_consistency_check as authority
import canonical_status_invariant_validator as canonical
import portfolio_pro_forma_risk_validator as risk
import proposal_patch_scope_validator as scope


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def packet() -> dict[str, Any]:
    surfaces = {
        "coverage_watchlist": "tracked",
        "execution_board": "almost_deployable / constructive",
        "portfolio_snapshot": "tactical_watch",
        "portfolio_config": "ALMOST",
    }
    return {
        "schema_version": 1,
        "generated_at_utc": "2026-05-11T00:00:00Z",
        "proposal_id": "test-001",
        "mutation_type": "canonical_status_move",
        "ticker_or_scope": "TEST",
        "current_state": {},
        "proposed_state": {},
        "why_now": "review-only proposal; no authority granted",
        "evidence": [],
        "source_freshness": {"overall_classification": "current", "trust_level": "clean"},
        "base_case": "review only",
        "bear_case": "review only",
        "risk_rule_check": {"status": "pass", "references": ["25% sector cap", "15% normal single-name ceiling", "speculative sleeve cap", "catalyst-window exception"]},
        "concentration_check": {"status": "pass", "single_name_after_pct": 10},
        "technical_gate": {"status": "pass"},
        "catalyst_gate": {"status": "clear"},
        "proposed_files_to_edit": ["03. Portfolio/Portfolio Snapshot.md"],
        "rollback_or_reversal_note": "discard if rejected",
        "stop_lines_triggered": [],
        "owner_decision_required": True,
        "owner_approval_granted": False,
        "apply_allowed": False,
        "canonical_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "trade_or_account_action_allowed": False,
        "current_status_tuple": dict(surfaces),
        "proposed_status_tuple": dict(surfaces),
        "affected_owner_surfaces": sorted(surfaces),
        "field_level_deltas": [
            {"owner_surface": "portfolio_snapshot", "field": "status", "from": "tactical_watch", "to": "tactical_watch", "mutation_class": "review_only"}
        ],
        "canonical_invariant_checks": {"status": "pass"},
        "sector_exposure_before_after": [{"sector": "Tech", "before_pct": 24, "after_pct": 24.5}],
        "correlated_sleeve_exposure_before_after": [{"group": "AI/mega-cap", "before_pct": 20, "after_pct": 21, "cap_pct": 30}],
        "sleeve_deltas": [{"sleeve": "core", "before_pct": 50, "after_pct": 50, "cap_pct": 70}],
        "current_cash_target_pct": 10,
        "proposed_cash_target_pct": 10,
    }


def write_packet(tmp: Path, data: dict[str, Any]) -> Path:
    path = tmp / "proposal.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def test_valid_packet(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        path = write_packet(Path(td), packet())
        expect(scope.build_report(path)["status"] == "ok", "valid packet should pass patch scope", errors)
        expect(canonical.build_report(path)["status"] == "ok", "valid packet should pass canonical invariants", errors)
        expect(risk.build_report(path)["status"] == "ok", "valid packet should pass risk validator", errors)
        expect(authority.build_report([path])["status"] == "ok", "valid packet should pass authority vocabulary", errors)


def test_failures(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as td:
        bad = packet()
        bad["proposed_files_to_edit"] = ["brokerage/account-orders.json"]
        path = write_packet(Path(td), bad)
        expect(scope.build_report(path)["status"] == "blocked", "brokerage path must block patch scope", errors)

        bad = packet()
        bad["proposed_status_tuple"]["execution_board"] = "deployable_now"
        bad["current_status_tuple"]["execution_board"] = "below_stop"
        path = write_packet(Path(td), bad)
        expect(canonical.build_report(path)["status"] == "blocked", "below_stop to deployable_now must block", errors)

        bad = packet()
        bad["sector_exposure_before_after"] = [{"sector": "Tech", "after_pct": 30}]
        path = write_packet(Path(td), bad)
        expect(risk.build_report(path)["status"] == "blocked", "sector cap breach must block risk validator", errors)

        bad = packet()
        bad["concentration_check"] = {"status": "pass", "single_name_after_pct": 18}
        path = write_packet(Path(td), bad)
        expect(risk.build_report(path)["status"] == "blocked", "single-name ceiling breach must block risk validator", errors)

        bad = packet()
        bad["why_now"] = "approval granted; execute trade"
        path = write_packet(Path(td), bad)
        expect(authority.build_report([path])["status"] == "blocked", "forbidden authority language must block", errors)


def main() -> int:
    errors: list[str] = []
    test_valid_packet(errors)
    test_failures(errors)
    if errors:
        print("portfolio_mutation_validators_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("portfolio_mutation_validators_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
