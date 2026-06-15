from pathlib import Path

from finance_ticker_card_refresh_gate import (
    build_commands,
    full_answer_rebuild_decision,
    semantic_digest,
)


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    summary_path = Path("tmp/test-card-summary.json")

    always_commands = [" ".join(cmd) for cmd in build_commands(True, summary_path, full_answer_mode="always")]
    changed_commands = [" ".join(cmd) for cmd in build_commands(True, summary_path, full_answer_mode="changed")]
    never_commands = [" ".join(cmd) for cmd in build_commands(True, summary_path, full_answer_mode="never")]

    expect(
        any("trade_grade_full_answer_assembler.py" in cmd for cmd in always_commands),
        "always mode must include the WF85 full-answer assembler",
        errors,
    )
    expect(
        not any("trade_grade_full_answer_assembler.py" in cmd for cmd in changed_commands),
        "changed mode static plan must stay on the fast path until runtime digest comparison",
        errors,
    )
    expect(
        not any("trade_grade_full_answer_assembler.py" in cmd for cmd in never_commands),
        "never mode must skip the WF85 full-answer assembler",
        errors,
    )

    digest_a = semantic_digest({"generated_at_utc": "one", "cards": [{"ticker": "A", "x": 1}]})
    digest_b = semantic_digest({"generated_at_utc": "two", "cards": [{"ticker": "A", "x": 1}]})
    digest_c = semantic_digest({"generated_at_utc": "two", "cards": [{"ticker": "A", "x": 2}]})
    expect(digest_a == digest_b, "semantic digest must ignore volatile generated timestamps", errors)
    expect(digest_a != digest_c, "semantic digest must change when semantic card content changes", errors)

    unchanged = full_answer_rebuild_decision("changed", digest_a, digest_b)
    changed = full_answer_rebuild_decision("changed", digest_a, digest_c)
    expect(unchanged["command_run"] is False, "changed mode must skip unchanged source digest", errors)
    expect(changed["command_run"] is True, "changed mode must run on changed source digest", errors)

    if errors:
        print("finance ticker-card refresh gate mode test failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("finance ticker-card refresh gate mode test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
