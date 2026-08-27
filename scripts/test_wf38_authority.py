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
    expect("CANONICAL_THESIS_NOTE" not in candidate_source, "candidate validator must not name Coverage and Watchlist as canonical thesis owner", errors)
    expect("thesis_block_exists" not in candidate_source, "candidate validator must not gate on Coverage and Watchlist heading presence", errors)
    expect("canonical_thesis_source" not in candidate_source + schema_source + contract_source, "candidate packet contract must not carry canonical_thesis_source wording", errors)
    expect("COVERAGE_UNIVERSE_PATH" not in dashboard_source, "dashboard validation must not parse Coverage and Watchlist as a live-state consistency surface", errors)
    expect("coverage_quickref_stale" not in dashboard_source, "dashboard validation must not emit Coverage and Watchlist quick-reference stale-state warnings", errors)


def test_workbook_nontechnical_owner_pointer(errors: list[str]) -> None:
    expect(
        workbook_export.owner_note_pointer_for_ticker("KTOS", technical_entitled=False) == "04. Research/Coverage and Watchlist.md",
        "non-technical names should point to Coverage and Watchlist",
        errors,
    )
    expect(
        workbook_export.owner_note_pointer_for_ticker("JPM", technical_entitled=True) == "03. Portfolio/Execution Board.md",
        "technical-entitled names should point to the Execution Board when no scorecard overrides it",
        errors,
    )


def test_promotion_review_only_boundary(errors: list[str]) -> None:
    expect(
        promotion_review_check.REVIEW_READY_GATE_PATTERN == {
            "thesis": "pass",
            "macro_regime": "pass",
            "technical": "pass",
            "catalyst": "clear",
            "risk_sizing": "warning",
        },
        "review-ready gate pattern should stay exact and conservative",
        errors,
    )

    reviews = {
        ticker: promotion_review_check.build_review(ticker)
        for ticker in ("JPM", "NVDA", "LLY", "CAT", "ETN", "GS")
    }

    for ticker, review in reviews.items():
        expect(review.get("trade_execution_authorized") is False, f"{ticker} review path must never authorize trade execution", errors)
        expect(review.get("canonical_mutation_allowed") is False, f"{ticker} review path must never authorize automatic canonical mutation", errors)
        expect(review.get("deployable_now_authorized") is False, f"{ticker} review path must never authorize deployable-now", errors)
        expect(review.get("authorization_required") is True, f"{ticker} review path must always require explicit owner authorization", errors)
        expect(review.get("non_authorizing") is True, f"{ticker} review path must stay non-authorizing", errors)
        expect(review.get("status") != "auto_approved", f"{ticker} review path must not emit auto_approved", errors)
        expect("auto_approval" not in review, f"{ticker} review path must not emit auto_approval blocks", errors)

    expect(
        any(review.get("blockers") for review in reviews.values()),
        "checked reviews should expose explicit fail-closed blockers for currently unready names",
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
    test_promotion_review_only_boundary(errors)
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
