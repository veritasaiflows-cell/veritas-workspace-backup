from __future__ import annotations

import pm_implementation_job_queue as queue
import pm_execution_loop as loop


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    template = {
        "proof_commands": [
            "python scripts\\trade_grade_decision_cards.py --write --validate",
            queue.PM_CONTROL_WRITE_DB_COMMAND,
        ]
    }
    filtered = queue.proof_commands_for_template(template)
    expect(queue.PM_CONTROL_WRITE_DB_COMMAND not in filtered, "duplicate PM control command must move to closeout", errors)
    expect(len(filtered) == 1, "non-PM proof command must remain", errors)

    only_pm = queue.proof_commands_for_template({"proof_commands": [queue.PM_CONTROL_WRITE_DB_COMMAND]})
    expect(only_pm == [queue.PM_CONTROL_WRITE_DB_COMMAND], "single PM-only proof must remain valid", errors)

    state = loop.worker_state(
        [{"job_id": "pm-test"}],
        [{"ok": True}],
        [{"ok": True, "command": "python scripts\\pm_control_packet.py --write --write-db --validate"}],
        executed=True,
        completion_ledger_result={"ok": True},
    )
    expect(state["candidate_selected"] is True, "worker state should record selection", errors)
    expect(state["proof_executed"] is True, "worker state should record proof execution", errors)
    expect(state["closeout_ledgered"] is True, "worker state should record ledger closeout", errors)
    expect(state["frontdoors_refreshed"] is True, "worker state should detect PM frontdoor refresh", errors)
    expect(state["job_resolved_or_completed"] is True, "worker state should report resolved job", errors)

    if errors:
        print("pm_execution_proof_reuse_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("pm_execution_proof_reuse_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
