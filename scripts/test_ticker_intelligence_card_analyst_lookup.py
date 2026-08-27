from __future__ import annotations

from ticker_intelligence_card import find_analyst_consensus_entry


def test_analyst_lookup_prefers_full_ticker_map_over_manual_review_queue() -> None:
    artifact = {
        "manual_review_queue": [
            {
                "ticker": "NVDA",
                "tier": "A",
                "status": "auto_sourced_yfinance",
                "source_url": "https://finance.yahoo.com/quote/NVDA/analysis",
            }
        ],
        "tickers": {
            "NVDA": {
                "status": "auto_sourced_yfinance",
                "consensus_rating": "Buy skew",
                "average_target": 298.9322,
                "median_target": 288.0,
                "high_target": 500.0,
                "low_target": 180.0,
                "strong_buy_count": 10,
                "buy_count": 49,
                "hold_count": 2,
                "sell_count": 1,
                "strong_sell_count": 0,
                "implied_upside_downside_pct": 41.88,
                "source_url": "https://finance.yahoo.com/quote/NVDA/analysis",
            }
        },
    }

    row = find_analyst_consensus_entry(artifact, "NVDA")

    assert row is not None
    assert row["average_target"] == 298.9322
    assert row["buy_count"] == 49
    assert row["strong_buy_count"] == 10
    assert row["source_url"] == "https://finance.yahoo.com/quote/NVDA/analysis"


def test_analyst_lookup_falls_back_to_generic_rows() -> None:
    artifact = {"rows": [{"ticker": "NVDA", "average_target": 300.0, "buy_count": 50}]}

    row = find_analyst_consensus_entry(artifact, "NVDA")

    assert row is not None
    assert row["average_target"] == 300.0
    assert row["buy_count"] == 50


if __name__ == "__main__":
    test_analyst_lookup_prefers_full_ticker_map_over_manual_review_queue()
    test_analyst_lookup_falls_back_to_generic_rows()
    print("ticker_intelligence_card_analyst_lookup: ok")
