#!/usr/bin/env python3
from __future__ import annotations

from types import SimpleNamespace

import finance_intelligence_router_qa as qa


def test_sql_first_retired_production_scope_is_clean() -> None:
    assert qa.sql_canon_production_answer_scope_ok([], {"ok": True})
    assert qa.sql_canon_legacy_answer_scope_ok([])


def test_sql_first_review_monitor_tier_a_state_is_clean() -> None:
    state = SimpleNamespace(
        auto_tier="Tier A",
        auto_state="A-WATCH",
        answer_scope="sql_first_review_monitor",
        production_scope_member=False,
        production_card_generation_allowed=False,
    )
    assert qa.sql_canon_ticker_state_scope_ok(state)


def test_sql_first_review_monitor_fails_if_authority_widens() -> None:
    state = SimpleNamespace(
        auto_tier="Tier A",
        auto_state="A-WATCH",
        answer_scope="sql_first_review_monitor",
        production_scope_member=False,
        production_card_generation_allowed=True,
    )
    assert not qa.sql_canon_ticker_state_scope_ok(state)


def test_wf78_legacy_coverage_allows_retired_zero_scope() -> None:
    assert qa.wf78_legacy_coverage_scope_ok([], ["AAPL"], [])
    assert not qa.wf78_legacy_coverage_scope_ok(["AAPL"], [], ["AAPL"])


if __name__ == "__main__":
    test_sql_first_retired_production_scope_is_clean()
    test_sql_first_review_monitor_tier_a_state_is_clean()
    test_sql_first_review_monitor_fails_if_authority_widens()
    test_wf78_legacy_coverage_allows_retired_zero_scope()
    print("ok")
