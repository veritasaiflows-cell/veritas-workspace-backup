from __future__ import annotations

from ticker_intelligence_card import build_period_aligned_fundamentals


def main() -> int:
    base = {
        "ticker": "ETN",
        "period_type": "quarterly",
        "period_end": "2026-03-31",
        "comparison_period_end": "2025-03-31",
        "revenue": 7_451_000_000.0,
        "net_income": 866_000_000.0,
        "diluted_eps": 2.22,
        "free_cash_flow": 314_000_000.0,
        "total_debt": 21_833_000_000.0,
        "roic_proxy_pct": 9.04,
        "enterprise_value": 194_943_320_064.0,
        "dividend_yield_pct": 0.24,
        "source": "yfinance",
    }
    claims = {
        "quarterly_metrics": {
            "period": "2026-06-30",
            "source_url": "https://example.invalid/etn-q2",
            "value": {
                "revenue": 8_500_000_000.0,
                "diluted_eps": 2.11,
                "operating_cash_flow": 1_100_000_000.0,
                "free_cash_flow": 874_000_000.0,
                "free_cash_flow_yoy_pct": 22.0,
            },
        },
        "growth_bridge": {
            "period": "2026-06-30",
            "value": {"reported_sales_growth_pct": 21.0},
        },
    }
    aligned, status = build_period_aligned_fundamentals(base, claims)
    assert status["status"] == "newer_official_period_normalized_metrics_catch_up_required"
    assert aligned["period_end"] == "2026-06-30"
    assert aligned["revenue"] == 8_500_000_000.0
    assert aligned["free_cash_flow"] == 874_000_000.0
    assert aligned["total_debt"] is None
    assert aligned["roic_proxy_pct"] is None
    assert aligned["dividend_yield_pct"] is None
    assert aligned["prior_normalized_metrics"]["period_end"] == "2026-03-31"

    bridge_claims = {
        "quarterly_metrics": {
            "period": "2026-06-30",
            "source_url": "https://www.sec.gov/Archives/edgar/data/1551182/000155118226000030/etn-20260630.htm",
            "value": {
                "official_period_bridge_verified": True,
                "period_bridge_validation": "matching_period_official_10q",
                "source_kind": "sec_10q_official_report",
                "comparison_period_end": "2025-06-30",
                "revenue": 8_531_000_000.0,
                "revenue_prior": 7_028_000_000.0,
                "revenue_yoy_pct": 21.3859,
                "net_income": 821_000_000.0,
                "net_income_prior": 982_000_000.0,
                "net_income_yoy_pct": -16.3951,
                "diluted_eps": 2.11,
                "diluted_eps_prior": 2.51,
                "eps_yoy_pct": -15.9363,
            },
        }
    }
    bridged, bridge_status = build_period_aligned_fundamentals(base, bridge_claims)
    assert bridge_status["status"] == "official_period_bridge_verified"
    assert bridge_status["normalized_metrics_stale"] is False
    assert bridge_status["normalized_provider_refresh_pending"] is True
    assert bridged["source"] == "official_sec_10q_period_bridge"
    assert bridged["revenue"] == 8_531_000_000.0
    assert bridged["revenue_prior"] == 7_028_000_000.0
    assert bridged["net_income"] == 821_000_000.0
    assert bridged["diluted_eps_prior"] == 2.51
    print("ticker card period alignment tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
