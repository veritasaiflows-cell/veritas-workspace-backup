from __future__ import annotations

from ticker_intelligence_card import (
    build_review_competitive_moat,
    build_review_thesis_context,
    effective_review_fresh_quote_required,
    review_post_close_quote_available,
    sector_record,
)


SECTOR_BOARD = {
    "sectors": [
        {"ticker": "XLF", "sector": "Financials", "relative_strength_vs_spy": {"20d": 2.1}},
        {"ticker": "XLI", "sector": "Industrials", "relative_strength_vs_spy": {"20d": 4.9}},
        {"ticker": "XLK", "sector": "Technology", "relative_strength_vs_spy": {"20d": 7.0}},
    ]
}


def test_exact_sector_match() -> None:
    row = sector_record(SECTOR_BOARD, "Financials")
    assert row is not None
    assert row["ticker"] == "XLF"
    assert row["sector_match_basis"] == "exact"


def test_exact_ticker_match() -> None:
    row = sector_record(SECTOR_BOARD, "XLK")
    assert row is not None
    assert row["sector"] == "Technology"
    assert row["sector_match_basis"] == "exact"


def test_custom_sector_alias_match() -> None:
    row = sector_record(SECTOR_BOARD, "Financial Infrastructure")
    assert row is not None
    assert row["ticker"] == "XLF"
    assert row["sector_query"] == "Financial Infrastructure"
    assert row["sector_match_basis"] == "alias:FINANCIAL INFRASTRUCTURE->FINANCIALS"


def test_defense_alias_uses_industrials_proxy() -> None:
    row = sector_record(SECTOR_BOARD, "Defense")
    assert row is not None
    assert row["ticker"] == "XLI"
    assert row["sector_match_basis"] == "alias:DEFENSE->INDUSTRIALS"


def test_review_thesis_uses_sourced_artifacts() -> None:
    sector = sector_record(SECTOR_BOARD, "Tech")
    ctx = build_review_thesis_context(
        "ABC",
        {
            "revenue_yoy_pct": 10.0,
            "eps_yoy_pct": 12.0,
            "free_cash_flow_yoy_pct": -3.0,
            "period_end": "2026-03-31",
            "source_tier": "aggregator_secondary",
        },
        {},
        sector,
        {"band_status": "IN_BAND"},
        [{"severity": "context"}],
        {"name": "ABC Corp"},
    )
    assert ctx["status"] == "synthesized_review_only_source_backed"
    assert "review-only" in ctx["thesis"]
    assert ctx["source_open_required"] is True
    assert ctx["synthesis_evidence"]


def test_etf_review_thesis_uses_instrument_profile() -> None:
    ctx = build_review_thesis_context(
        "ETF",
        {
            "instrument_type": "etf_or_macro_proxy",
            "sector": "International Equity",
            "portfolio_role": "etf_monitor",
            "coverage_lane": "watch",
        },
        {},
        None,
        {"band_status": "WATCH"},
        [],
        {"name": "ETF Fund"},
    )
    assert ctx["status"] == "synthesized_review_only_source_backed"
    assert "ETF/macro proxy" in ctx["thesis"]
    assert ctx["synthesis_evidence"][0]["label"] == "etf_or_macro_proxy_profile"


def test_competitive_moat_requires_evidence() -> None:
    moat = build_review_competitive_moat(
        {
            "ticker": "ABC",
            "operating_margin_pct": 30.0,
            "net_margin_pct": 20.0,
            "roic_proxy_pct": 15.0,
            "period_end": "2026-03-31",
            "source_tier": "aggregator_secondary",
        },
        {},
        None,
        {"name": "ABC Corp"},
        "equity",
    )
    assert moat["status"] == "partially_structured_source_backed_review_required"
    assert moat["evidence"]
    assert "not a final" in moat["summary"]


def test_post_close_quote_clears_review_freshness_requirement() -> None:
    readiness = {"fresh_quote_required": True}
    post_close_quote = {
        "market_date": "2026-06-18",
        "retrieved_at_utc": "2026-06-20T02:00:22Z",
        "source": "yfinance",
    }
    assert review_post_close_quote_available(post_close_quote) is True
    assert effective_review_fresh_quote_required(readiness, post_close_quote) is False


def test_missing_post_close_quote_keeps_review_freshness_requirement() -> None:
    readiness = {"fresh_quote_required": True}
    assert review_post_close_quote_available(None) is False
    assert effective_review_fresh_quote_required(readiness, None) is True


if __name__ == "__main__":
    test_exact_sector_match()
    test_exact_ticker_match()
    test_custom_sector_alias_match()
    test_defense_alias_uses_industrials_proxy()
    test_review_thesis_uses_sourced_artifacts()
    test_etf_review_thesis_uses_instrument_profile()
    test_competitive_moat_requires_evidence()
    test_post_close_quote_clears_review_freshness_requirement()
    test_missing_post_close_quote_keeps_review_freshness_requirement()
    print("ok")
