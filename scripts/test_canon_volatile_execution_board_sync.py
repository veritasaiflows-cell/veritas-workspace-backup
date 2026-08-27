from __future__ import annotations

import canon_volatile_execution_board_sync as sync


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_sql_first_thin_board_short_circuits_table_mutation(errors: list[str]) -> None:
    ok = sync.sql_first_thin_board_sync_decision(
        {
            "sql_first_thin_board_detected": True,
            "sql_first_thin_board_allowed": True,
        }
    )
    expect(ok["short_circuit_note_mutation"] is True, f"thin board should short-circuit table mutation, got {ok}", errors)
    expect(ok["status"] == "ok", f"allowed thin board should be ok, got {ok}", errors)
    blocked = sync.sql_first_thin_board_sync_decision(
        {
            "sql_first_thin_board_detected": True,
            "sql_first_thin_board_allowed": False,
        }
    )
    expect(blocked["status"] == "blocked", f"blocked thin board contract should block, got {blocked}", errors)
    legacy = sync.sql_first_thin_board_sync_decision({"sql_first_thin_board_detected": False})
    expect(
        legacy["short_circuit_note_mutation"] is False and legacy["status"] == "legacy_execution_board_table",
        f"non-thin board should use legacy table sync, got {legacy}",
        errors,
    )


def test_thin_board_row_keeps_review_only_values(errors: list[str]) -> None:
    row = sync.build_thin_board_row(
        "GS",
        {"entry_bands": {"GS": {"low": 971.53, "high": 1048.14, "stop": 928.97}}},
        {"close": 1096.56, "data_date": "2026-06-18", "below_stop": False},
        {"action_state": "ALMOST DEPLOYABLE"},
        {},
    )
    expect(row["ticker"] == "GS", f"ticker should pass through, got {row}", errors)
    expect(row["band"] == "971.53-1048.14", f"band should format, got {row}", errors)
    expect(row["stop"] == "928.97", f"stop should format, got {row}", errors)
    expect(row["action_state"] == "ALMOST DEPLOYABLE", f"action should pass through, got {row}", errors)


def main() -> int:
    errors: list[str] = []
    test_sql_first_thin_board_short_circuits_table_mutation(errors)
    test_thin_board_row_keeps_review_only_values(errors)
    if errors:
        print("canon_volatile_execution_board_sync_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("canon_volatile_execution_board_sync_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
