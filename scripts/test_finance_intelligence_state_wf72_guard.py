from __future__ import annotations

from finance_intelligence_state import assert_wf72_support_only_answer_route


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def must_raise(source: str, contract: dict, errors: list[str]) -> None:
    try:
        assert_wf72_support_only_answer_route(source, contract)
    except AssertionError:
        return
    errors.append(f"expected WF72 guard to reject source={source}")


def main() -> int:
    errors: list[str] = []
    good_contract = {
        "wf72_sql_cache_is_support_only": True,
        "wf72_finance_answer_front_door_allowed": False,
        "prefer_wf85_full_answer_assembler_when_available": True,
    }
    assert_wf72_support_only_answer_route("wf85_full_answer_assembler", good_contract)
    assert_wf72_support_only_answer_route("wf84_canonical_data_plane", good_contract)
    must_raise("wf72_sql_cache", good_contract, errors)
    must_raise("wf72_entry_stop_reference", good_contract, errors)
    must_raise("wf85_full_answer_assembler", {**good_contract, "wf72_sql_cache_is_support_only": False}, errors)
    must_raise("wf85_full_answer_assembler", {**good_contract, "wf72_finance_answer_front_door_allowed": True}, errors)
    must_raise("wf85_full_answer_assembler", {**good_contract, "prefer_wf85_full_answer_assembler_when_available": False}, errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: WF72 finance-answer guard rejects answer ownership")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
