#!/usr/bin/env python3
"""SQL-canon retirement tests for ticker-card and refresh gates."""
from __future__ import annotations

from finance_sql_canon_access import SecurityState
import finance_ticker_card_refresh_gate as refresh_gate
import ticker_intelligence_card as ticker_card
import wf85_market_hours_refresh_readiness as wf85_readiness


def security_state(ticker: str, allowed: bool = False) -> SecurityState:
    return SecurityState(
        ticker=ticker,
        name=ticker,
        instrument_type="equity",
        sector=None,
        industry=None,
        universe_scope="production_current_42",
        legacy_tier="A",
        legacy_production_42=True,
        production_scope_member=False,
        production_scope_source=None,
        tier_ab_decision_scope=None,
        compatibility_reason="legacy_42_advisory_only",
        sql_tier=None,
        sql_tier_state=None,
        tier_decision_scope=None,
        auto_tier="Tier A",
        auto_state="A-WATCH",
        answer_scope="legacy_42",
        production_card_generation_allowed=allowed,
        has_production_card=False,
        provider_status=None,
    )


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

    def field_family_summary(self):
        return {"status": "ok"}

    def ticker_states(self, tickers):
        return {str(ticker): security_state(str(ticker)) for ticker in tickers}

    def ticker_state(self, ticker):
        return security_state(str(ticker))

    def reference_level(self, _ticker):
        return None

    def evidence_freshness(self, _ticker):
        return None


def test_ticker_card_keeps_legacy_42_advisory_only(monkeypatch) -> None:
    monkeypatch.setattr(ticker_card, "FinanceSqlCanonAccess", Legacy42Client)

    result = ticker_card.load_sql_canon_inputs(["T00"])
    context = result["context"]

    assert context["status"] == "ok"
    assert context["production_answer_count"] == 0
    assert context["legacy_production_answer_count"] == 42
    assert context["legacy_42_retired_from_blocking"] is True
    assert context["legacy_42_count_advisory_only"] is True
    assert context["validation"]["warnings"] == [
        "production_grade_set_empty_wait_for_decision_grade_gates"
    ]


def test_wf85_readiness_uses_shared_sql_first_route_context(monkeypatch) -> None:
    def fake_context(*, consumer: str, db_path):
        return {
            "status": "ok",
            "consumer": consumer,
            "production_answer_count": 0,
            "legacy_production_answer_count": 42,
            "legacy_42_retired_from_blocking": True,
            "legacy_42_count_advisory_only": True,
            "validation": {
                "status": "ok",
                "warnings": ["production_grade_set_empty_wait_for_decision_grade_gates"],
            },
        }

    monkeypatch.setattr(wf85_readiness, "strategic_answer_route_context", fake_context)

    context = wf85_readiness.finance_sql_canon_context()

    assert context["status"] == "ok"
    assert context["consumer"] == "wf85_market_hours_refresh_readiness"
    assert context["production_answer_count"] == 0
    assert context["legacy_production_answer_count"] == 42
    assert context["legacy_42_retired_from_blocking"] is True
    assert context["legacy_42_count_advisory_only"] is True


def test_refresh_gate_does_not_promote_legacy_42_to_effective_scope(monkeypatch) -> None:
    monkeypatch.setattr(refresh_gate, "FinanceSqlCanonAccess", Legacy42Client)
    base_scope = {
        ticker: {
            "ticker": ticker,
            "production_answer_path_member": True,
            "thin_monitor_row": False,
            "tier": "A",
            "universe_scope": "production_current_42",
        }
        for ticker in Legacy42Client.tickers
    }

    context, overlay = refresh_gate.sql_canon_scope_index(base_scope)

    assert context["status"] == "ok"
    assert context["legacy_42_retired_from_blocking"] is True
    assert context["legacy_42_count_advisory_only"] is True
    assert context["production_answer_count"] == 0
    assert context["legacy_production_answer_count"] == 42
    assert context["effective_production_answer_count"] == 0
    assert context["validation"]["warnings"][0] == "production_grade_set_empty_wait_for_decision_grade_gates"
    assert not any(row["production_answer_path_member"] for row in overlay.values())


def test_low_confidence_reference_band_requires_reference_refresh() -> None:
    assert ticker_card.low_confidence_reference_band_requires_refresh(
        {"auto_tier": "Tier A"},
        {"reference_confidence": 2},
        "BELOW_STOP",
    ) is True
    assert ticker_card.low_confidence_reference_band_requires_refresh(
        {"auto_tier": "Tier A"},
        {"reference_confidence": 2},
        "BELOW_STOP",
    ) is True
    assert ticker_card.low_confidence_reference_band_requires_refresh(
        {"auto_tier": "Tier A"},
        {"reference_confidence": 3},
        "BELOW_STOP",
    ) is False
    assert ticker_card.low_confidence_reference_band_requires_refresh(
        {"auto_tier": "Tier B"},
        {"reference_confidence": 2},
        "BELOW_STOP",
    ) is False


def test_post_close_overlay_preserves_stale_reference_band_with_current_technicals() -> None:
    card = {
        "ticker": "ACN",
        "price_band_stop": {
            "entry_band_low": 224.58,
            "entry_band_high": 235.32,
            "stop_or_invalidation": 215.99,
            "band_status": ticker_card.STALE_REFERENCE_BAND,
            "reference_band_refresh_required": True,
            "fresh_quote_required": True,
            "staleness_note": "refresh required",
        },
        "technical_posture": {
            "latest_close": 178.49,
            "ma20": 185.0,
            "ma50": 190.0,
            "ma200": 200.0,
            "data_date": "2026-08-14",
        },
    }
    updated = ticker_card.apply_post_close_price_overlay(
        card,
        {
            "post_close_final_quote_index": {
                "ACN": {"ticker": "ACN", "status": "ok", "close": 178.49, "market_date": "2026-08-14"}
            }
        },
    )
    assert updated["price_band_stop"]["band_status"] == ticker_card.STALE_REFERENCE_BAND
    assert updated["price_band_stop"]["fresh_quote_required"] is True
    assert updated["price_band_stop"]["staleness_note"] == "refresh required"
