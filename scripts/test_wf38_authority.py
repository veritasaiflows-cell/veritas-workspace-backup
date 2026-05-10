from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import candidate_packet_validator
import board_state_contract
import dashboard_validation
import generate_entry_band_status
import promotion_review_check
import validate_portfolio_config
import workbook_export


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_coverage_universe_not_deployment_authority(errors: list[str]) -> None:
    candidate_source = Path(candidate_packet_validator.__file__).read_text(encoding="utf-8")
    dashboard_source = Path(dashboard_validation.__file__).read_text(encoding="utf-8")
    schema_source = (SCRIPTS_DIR / "schemas" / "candidate_packet_schema.json").read_text(encoding="utf-8")
    contract_source = (SCRIPTS_DIR.parent / "06. Playbooks" / "Watchlist Promotion Candidate Packet Contract.md").read_text(encoding="utf-8")
    config_source = (SCRIPTS_DIR.parent / "tmp" / "portfolio-config.json").read_text(encoding="utf-8")
    expect("CANONICAL_THESIS_NOTE" not in candidate_source, "candidate validator must not name Coverage Universe as canonical thesis owner", errors)
    expect("thesis_block_exists" not in candidate_source, "candidate validator must not gate on Coverage Universe heading presence", errors)
    expect("canonical_thesis_source" not in candidate_source + schema_source + contract_source, "candidate packet contract must not carry canonical_thesis_source wording", errors)
    expect("Coverage Universe.md" not in config_source, "tracked_universe source_of_truth must not include Coverage Universe", errors)
    expect("COVERAGE_UNIVERSE_PATH" not in dashboard_source, "dashboard validation must not parse Coverage Universe as a live-state consistency surface", errors)
    expect("coverage_quickref_stale" not in dashboard_source, "dashboard validation must not emit Coverage Universe quick-reference stale-state warnings", errors)


def test_workbook_nontechnical_owner_pointer(errors: list[str]) -> None:
    expect(
        workbook_export.owner_note_pointer_for_ticker("KTOS", technical_entitled=False) == "02. Markets/Watchlist.md",
        "non-technical names should point to Watchlist, not Coverage Universe",
        errors,
    )
    expect(
        workbook_export.owner_note_pointer_for_ticker("JPM", technical_entitled=True) == "03. Portfolio/Technical Entry and Invalidation Sheet.md",
        "technical-entitled names should point to the Technical Entry Sheet when no scorecard overrides it",
        errors,
    )


def test_promotion_auto_approval_boundary(errors: list[str]) -> None:
    expect(
        promotion_review_check.AUTO_APPROVAL_GATE_PATTERN == {
            "thesis": "pass",
            "macro_regime": "pass",
            "technical": "pass",
            "catalyst": "clear",
            "risk_sizing": "warning",
        },
        "auto-approval gate pattern should stay exact and conservative",
        errors,
    )

    reviews = {
        ticker: promotion_review_check.build_review(ticker)
        for ticker in ("JPM", "NVDA", "LLY", "CAT", "ETN", "GS")
    }

    for ticker, review in reviews.items():
        expect(review.get("trade_execution_authorized") is False, f"{ticker} review path must never authorize trade execution", errors)
        expect(review.get("canonical_mutation_allowed") is False, f"{ticker} review path must never authorize automatic canonical mutation", errors)
        if review.get("status") != "auto_approved":
            expect(review.get("deployable_now_authorized") is False, f"{ticker} must fail closed unless every exact auto-approval gate is satisfied", errors)

    live_auto_approved = [review for review in reviews.values() if review.get("status") == "auto_approved"]
    if live_auto_approved:
        approved = live_auto_approved[0]
        expect(approved.get("deployable_now_authorized") is True, "an auto-approved review should authorize deployable-now status inside the workspace review layer", errors)
        expect(approved.get("automated_queue_judgment") == "approve for deployable-now", "an auto-approved review should emit the deployable-now queue judgment", errors)
        expect(not approved.get("auto_approval", {}).get("blockers"), "an auto-approved review should not retain auto-approval blockers", errors)
    else:
        expect(
            any(review.get("blockers") for review in reviews.values()),
            "if no live name auto-approves, at least one checked review should expose explicit fail-closed blockers",
            errors,
        )

    nvda = reviews["NVDA"]
    expect(nvda.get("deployable_now_authorized") is False, "NVDA must not auto-authorize when live promotion gates are not clean", errors)

    lly = reviews["LLY"]
    expect(lly.get("coverage_lane") == "watch", "LLY should remain a watch-lane review-prep candidate", errors)
    expect(lly.get("deployable_now_authorized") is False, "LLY must not auto-authorize while it remains watch-lane only", errors)


def test_workflow_state_vocab_contract(errors: list[str]) -> None:
    expect("PROMOTION REVIEW" in validate_portfolio_config.APPROVED_WORKFLOW_STATES, "portfolio config validator must allow PROMOTION REVIEW workflow_state", errors)
    expect("DEPLOYED" in validate_portfolio_config.APPROVED_WORKFLOW_STATES, "portfolio config validator must allow DEPLOYED workflow_state", errors)
    expect(board_state_contract.canonical_action_state("PROMOTION REVIEW") == "ALMOST DEPLOYABLE", "board-state contract should normalize PROMOTION REVIEW to a review/actionable canonical state", errors)
    expect(board_state_contract.canonical_action_state("DEPLOYED") == "DEPLOYABLE NOW", "board-state contract should normalize DEPLOYED to deployable-now semantics", errors)
    fallback_targets = board_state_contract.execution_priority_quote_targets({
        "tracked_universe": {
            "JPM": {"coverage_lane": "execution", "daily_technical_priority": True, "workflow_state": "PROMOTION REVIEW"}
        }
    })
    expect(bool(fallback_targets) and fallback_targets[0].get("key") == "JPM", "PROMOTION REVIEW workflow_state should stay eligible for execution-priority fallback targeting", errors)
    expect(generate_entry_band_status.WORKFLOW_COLOR.get("PROMOTION REVIEW") == "#f59e0b", "entry-band status should color PROMOTION REVIEW explicitly", errors)


def main() -> int:
    errors: list[str] = []
    test_coverage_universe_not_deployment_authority(errors)
    test_workbook_nontechnical_owner_pointer(errors)
    test_promotion_auto_approval_boundary(errors)
    test_workflow_state_vocab_contract(errors)
    if errors:
        print("wf38_authority_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf38_authority_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
