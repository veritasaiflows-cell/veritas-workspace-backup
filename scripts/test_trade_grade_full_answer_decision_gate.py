from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import trade_grade_full_answer_assembler as mod


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    repair = {
        "decision_state": "evidence_repair",
        "primary_state": "promotion_vetoed",
        "queue_state": "promotion_vetoed",
        "decision_state_reason": ["current opportunity digest blocked/deferred"],
    }
    gate = mod.decision_grade_gate(repair)
    expect(gate["decision_grade_claim_allowed"] is False, "evidence repair must not allow decision-grade claim", errors)
    expect(gate["decision_grade_status"] == "not_decision_grade_yet", "repair state should be not decision-grade", errors)
    expect(gate["specific_repair_required"] == "promotion_veto_must_clear_before_review_ready", "promotion veto repair reason", errors)

    ready = mod.decision_grade_gate({"decision_state": "review_ready", "primary_state": "ready", "queue_state": "ready"})
    expect(ready["decision_grade_claim_allowed"] is True, "review_ready can allow review-ready claim", errors)
    expect(ready["capital_or_execution_authority"] is False, "gate never grants execution authority", errors)

    sections = mod.build_sections("TEST", {}, {"sections": {}, "drillback": []}, repair)
    summary = mod.section_summary(sections["decision_state"])
    expect("not_decision_grade_yet" in summary, "decision-state summary should expose gate", errors)
    text = mod.human_answer_text("TEST", sections, repair, mod.trade_grade(repair, {}), mod.owner_action(repair))
    expect("Decision-grade gate: not_decision_grade_yet" in text, "human answer should expose gate", errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("trade_grade_full_answer_decision_gate_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
