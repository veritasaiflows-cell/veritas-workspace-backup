from __future__ import annotations

import trade_grade_os_freshness_cron_runner as runner


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    names = [step[0] for step in runner.command_plan()]
    cards_only = [step[0] for step in runner.command_plan(["cards"])]

    required = [
        "wf84_canonical_data_plane",
        "wf85_decision_cards",
        "wf85_full_answer_assembler",
        "wf84_canonical_data_plane_post_full_answer",
        "wf84_wf85_full_answer_parity",
    ]
    for name in required:
        expect(name in names, f"missing runner step: {name}", errors)

    if not errors:
        expect(
            names.index("wf84_canonical_data_plane") < names.index("wf85_decision_cards"),
            "WF84 must rebuild before WF85 cards",
            errors,
        )
        expect(
            names.index("wf85_decision_cards") < names.index("wf85_full_answer_assembler"),
            "WF85 cards must rebuild before full-answer assembler",
            errors,
        )
        expect(
            names.index("wf85_full_answer_assembler") < names.index("wf84_canonical_data_plane_post_full_answer"),
            "WF84 section context must refresh after full-answer assembler",
            errors,
        )
        expect(
            names.index("wf84_canonical_data_plane_post_full_answer") < names.index("wf84_wf85_full_answer_parity"),
            "Full-answer parity must run after the post-assembler WF84 rebuild",
            errors,
        )

    expect(
        "wf85_full_answer_assembler" in runner.EXPECTED_ARTIFACTS,
        "runner expected artifacts must include the full-answer assembler rollup",
        errors,
    )
    expect("wf85_decision_cards" in cards_only, "cards component must include decision-card build", errors)
    expect("wf85_full_answer_assembler" not in cards_only, "cards component must not include full-answer assembler", errors)

    digest_a = runner.semantic_digest({"generated_at_utc": "one", "rows": [{"ticker": "A", "score": 1}]})
    digest_b = runner.semantic_digest({"generated_at_utc": "two", "rows": [{"ticker": "A", "score": 1}]})
    digest_c = runner.semantic_digest({"generated_at_utc": "two", "rows": [{"ticker": "A", "score": 2}]})
    expect(digest_a == digest_b, "semantic digest must ignore volatile timestamps", errors)
    expect(digest_a != digest_c, "semantic digest must change on semantic input changes", errors)

    unchanged = runner.full_answer_rebuild_decision("changed", digest_a, digest_b)
    changed = runner.full_answer_rebuild_decision("changed", digest_a, digest_c)
    expect(unchanged["command_run"] is False, "changed mode must skip unchanged full-answer inputs", errors)
    expect(changed["command_run"] is True, "changed mode must run changed full-answer inputs", errors)

    if errors:
        print("trade_grade_os_freshness_cron_runner_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("trade_grade_os_freshness_cron_runner_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
