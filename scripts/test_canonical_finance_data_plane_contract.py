#!/usr/bin/env python3
"""Focused regressions for WF84 data-plane contract active scope."""
from __future__ import annotations

import canonical_finance_data_plane_contract as contract


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def valid_table() -> list[dict[str, object]]:
    return [{"name": "sample", "primary_key": ["id"], "fields": [["id", "TEXT", False, "id"]]}]


def run_dynamic_scope_test(errors: list[str]) -> None:
    original_load_json = contract.load_json
    original_sqlite_count = contract.sqlite_count
    original_scope_profile = contract.finance_state_scope_profile
    try:
        contract.load_json = lambda path: {  # type: ignore[assignment]
            "summary": {"active_ticker_count": 3},
            "rows": [{"ticker": "AAA"}, {"ticker": "BBB"}, {"ticker": "CCC"}],
        }
        contract.sqlite_count = lambda db_path, table: 3  # type: ignore[assignment]
        contract.finance_state_scope_profile = lambda rows: {  # type: ignore[assignment]
            "scope_compatibility_allowed": True,
            "router_only_count": 0,
            "finance_only_count": 0,
        }
        validation = contract.build_validation([], valid_table())
        expect(validation["status"] == "ok", "three-row dynamic active scope should validate", errors)
        expect(
            validation["observed_counts"]["expected_active_tickers"] == 3,
            "expected active ticker count should come from router summary",
            errors,
        )
    finally:
        contract.load_json = original_load_json  # type: ignore[assignment]
        contract.sqlite_count = original_sqlite_count  # type: ignore[assignment]
        contract.finance_state_scope_profile = original_scope_profile  # type: ignore[assignment]


def run_router_mismatch_test(errors: list[str]) -> None:
    original_load_json = contract.load_json
    original_sqlite_count = contract.sqlite_count
    original_scope_profile = contract.finance_state_scope_profile
    try:
        contract.load_json = lambda path: {  # type: ignore[assignment]
            "summary": {"active_ticker_count": 3},
            "rows": [{"ticker": "AAA"}, {"ticker": "BBB"}],
        }
        contract.sqlite_count = lambda db_path, table: 3  # type: ignore[assignment]
        contract.finance_state_scope_profile = lambda rows: {  # type: ignore[assignment]
            "scope_compatibility_allowed": True,
            "router_only_count": 0,
            "finance_only_count": 0,
        }
        validation = contract.build_validation([], valid_table())
        expect(validation["status"] == "blocked", "router row-count mismatch should block", errors)
        expect(
            "router_active_count_row_mismatch:3!=2" in validation["errors"],
            "router row-count mismatch should be explicit",
            errors,
        )
    finally:
        contract.load_json = original_load_json  # type: ignore[assignment]
        contract.sqlite_count = original_sqlite_count  # type: ignore[assignment]
        contract.finance_state_scope_profile = original_scope_profile  # type: ignore[assignment]


def main() -> int:
    errors: list[str] = []
    run_dynamic_scope_test(errors)
    run_router_mismatch_test(errors)
    if errors:
        print("canonical_finance_data_plane_contract_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("canonical_finance_data_plane_contract_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
