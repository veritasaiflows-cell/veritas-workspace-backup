#!/usr/bin/env python3
"""Targeted WF61 tests for the small/mid-cap regime feed producer."""

from __future__ import annotations

import unittest

import small_mid_cap_regime_feed as feed


def series(start: float, drift: float, days: int = 230, *, volume: int = 1_000_000) -> list[dict]:
    rows = []
    value = start
    for idx in range(days):
        value += drift
        rows.append({
            "date": f"2026-05-{(idx % 28) + 1:02d}",
            "close": round(value, 4),
            "high": round(value * 1.01, 4),
            "low": round(value * 0.99, 4),
            "volume": volume,
        })
    rows[-1]["date"] = "2026-05-13"
    return rows


def stale_series(start: float, drift: float, days: int = 230, *, volume: int = 1_000_000) -> list[dict]:
    rows = series(start, drift, days, volume=volume)
    for idx, row in enumerate(rows):
        row["date"] = f"2026-03-{(idx % 28) + 1:02d}"
    rows[-1]["date"] = "2026-03-31"
    return rows


def fake_histories() -> dict[str, list[dict]]:
    data = {
        "SPY": series(100, 0.20, volume=80_000_000),
        "QQQ": series(100, 0.25, volume=50_000_000),
    }
    for item in feed.UNIVERSE:
        data[item["ticker"]] = series(50, 0.15, volume=2_000_000)
    data["IWM"] = series(40, 0.45, volume=30_000_000)
    data["IJR"] = series(45, 0.42, volume=5_000_000)
    data["SLV"] = series(25, 0.35, volume=40_000_000)
    data["CPER"] = series(20, 0.30, volume=10_000)
    data["USO"] = series(80, -0.20, volume=3_000_000)
    return data


def fetcher_for(data: dict[str, list[dict]]):
    def _fetch(ticker: str):
        rows = data.get(ticker, [])
        if not rows:
            return [], f"{ticker}: missing fixture"
        return rows, None
    return _fetch


class SmallMidCapRegimeFeedTests(unittest.TestCase):
    def test_universe_authority_and_review_only_recommendations(self):
        output = feed.build_feed("post-close", fetcher_for(fake_histories()))
        self.assertEqual(output["consumer_posture"], "review_only")
        self.assertEqual(len(output["proxies"]), len(feed.UNIVERSE))
        self.assertTrue(all(value is False for value in output["authority"].values()))
        tickers = [row["ticker"] for row in output["proxies"]]
        self.assertEqual(tickers, [item["ticker"] for item in feed.UNIVERSE])
        iwm = next(row for row in output["proxies"] if row["ticker"] == "IWM")
        self.assertEqual(iwm["regime_label"], "improving")
        self.assertIn("research packet", iwm["owner_gated_recommendation"])
        self.assertFalse(output["authority"]["portfolio_mutation_allowed"])

    def test_commodity_probe_carries_liquidity_and_tactical_warning(self):
        output = feed.build_feed("post-close", fetcher_for(fake_histories()))
        cper = next(row for row in output["proxies"] if row["ticker"] == "CPER")
        self.assertTrue(cper["liquidity_warning"])
        self.assertEqual(cper["regime_label"], "blocked")
        self.assertTrue(any("Tactical commodity expression" in warning for warning in cper["warnings"]))
        self.assertIn("reject-bench", cper["owner_gated_recommendation"])

    def test_missing_benchmark_blocks_relative_strength_contract(self):
        data = fake_histories()
        data.pop("SPY")
        output = feed.build_feed("post-close", fetcher_for(data))
        self.assertEqual(output["status"], "blocked")
        self.assertTrue(any("SPY" in error for error in output["errors"]))

    def test_stale_market_data_degrades_feed(self):
        data = {ticker: stale_series(100, 0.10, volume=50_000_000) for ticker in ["SPY", "QQQ"]}
        for item in feed.UNIVERSE:
            data[item["ticker"]] = stale_series(50, 0.08, volume=2_000_000)
        output = feed.build_feed("post-close", fetcher_for(data))
        self.assertEqual(output["status"], "degraded")
        self.assertFalse(output["market_data_fresh_enough"])
        self.assertEqual(output["market_data_as_of"], "2026-03-31")
        self.assertTrue(any("market data stale" in warning for warning in output["warnings"]))

    def test_insufficient_benchmark_history_blocks_feed(self):
        data = fake_histories()
        data["QQQ"] = data["QQQ"][-20:]
        output = feed.build_feed("post-close", fetcher_for(data))
        self.assertEqual(output["status"], "blocked")
        self.assertTrue(any("QQQ benchmark has only" in error for error in output["errors"]))

    def test_markdown_mentions_review_only_authority(self):
        output = feed.build_feed("post-close", fetcher_for(fake_histories()))
        md = feed.render_markdown(output)
        self.assertIn("Review Only", md)
        self.assertIn("no portfolio mutation", md)
        self.assertIn("IWM", md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
