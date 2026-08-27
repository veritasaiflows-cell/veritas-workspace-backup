#!/usr/bin/env python3
"""SQL-canon retirement tests for WF85 decision cards."""
from __future__ import annotations

import trade_grade_decision_cards as decision_cards


class Legacy42Client:
    tickers = [f"T{i:02d}" for i in range(42)]

    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def validate(self):
        return {"status": "ok", "errors": []}

    def production_answer_tickers(self):
        return []

    def legacy_production_answer_tickers(self):
        return list(self.tickers)

    def migration_registry_summary(self):
        return {"status": "ok"}


def test_decision_cards_keep_legacy_42_advisory_only(monkeypatch) -> None:
    monkeypatch.setattr(decision_cards, "FinanceSqlCanonAccess", Legacy42Client)
    monkeypatch.setattr(decision_cards, "p0_registry_lane_status", lambda _registry: {"ok": True, "errors": []})
    cards = [
        {"ticker": ticker, "wf84_scope": {"production_answer_path_member": True}}
        for ticker in Legacy42Client.tickers
    ]

    context = decision_cards.sql_canon_scope_context(cards)

    assert context["status"] == "ok"
    assert context["legacy_42_retired_from_blocking"] is True
    assert context["legacy_42_count_advisory_only"] is True
    assert context["sql_canon_production_answer_count"] == 0
    assert context["sql_canon_legacy_production_answer_count"] == 42
    assert context["effective_production_answer_count"] == 0
    assert context["validation"]["warnings"] == [
        "production_grade_set_empty_wait_for_decision_grade_gates",
        "legacy_wf84_answer_path_differs_from_strategic_sql_first_scope",
    ]
