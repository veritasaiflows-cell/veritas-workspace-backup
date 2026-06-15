#!/usr/bin/env python3
"""Targeted WF53 tests for the sector expansion board producer."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sector_expansion_board as seb


PROMOTION_QUEUE = """# Promotion Review Queue

| Candidate | Proposed lane | Review owner | Gate 1 thesis | Gate 2 macro/regime | Gate 3 technical | Gate 4 catalyst | Gate 5 risk/sizing | Blocking gate | Automated queue judgment | Next action | Last reviewed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ETN | execution conditional add | Veritas / Randall final judgment | pass | pass | pass | pass | warning | size/correlation discipline | approved conditional add | Explicit owner promotion granted; manual only. | 2026-05-09 |
| JPM | execution conditional add | Veritas / Randall final judgment | pass | pass | warning | pass | warning | below formal band / near invalidation | approval recorded; trigger not live | Keep approval recorded; no deployable-now until band reclaim. | 2026-05-10 |
| NVDA | execution promotion review | Veritas / Randall final judgment | pass | pass | pass | warning | warning | catalyst timing / crowding / sizing | hold in promotion review | Keep out of deployable-now while earnings remains inside timing-sensitive window | 2026-05-06 |
| GS | execution | Veritas / Randall final judgment | pass | pass | pass | pass | warning | risk/sizing / peer priority | hold in promotion review | Keep secondary to JPM unless explicit review says otherwise | 2026-05-06 |
| LLY | execution review prep | Veritas / Randall final judgment | pass | warning | warning | pass | warning | sizing / explicit promotion judgment | hold in promotion review | Keep watch-lane only until pullback quality and explicit promotion/sizing review justify a real lane change | 2026-05-07 |
| CAT | execution review prep | Veritas / Randall final judgment | warning | pass | warning | pass | warning | technical drift / sizing | hold in promotion review | Keep watch-lane only until pullback quality and explicit promotion/sizing review justify a real lane change | 2026-05-07 |
"""


def series(start: float, drift: float, days: int = 60) -> list[dict]:
    rows = []
    value = start
    for idx in range(days):
        value += drift
        rows.append({"date": f"2026-03-{(idx % 28) + 1:02d}", "close": round(value, 4)})
    rows[-1]["date"] = "2026-05-08"
    return rows


def fake_histories() -> dict[str, list[dict]]:
    data = {"SPY": series(100, 1)}
    for ticker in seb.SECTOR_ETFS:
        data[ticker] = series(50, 0.7)
    data["XLK"] = series(50, 1.8)
    data["XLI"] = series(50, 1.3)
    data["XLV"] = series(80, 1.6)
    data["XLE"] = series(60, -0.2)
    return data


def fetcher_for(data: dict[str, list[dict]]):
    def _fetch(ticker: str):
        rows = data.get(ticker, [])
        if not rows:
            return [], f"{ticker}: missing fixture"
        return rows, None
    return _fetch


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class TempWorkspace:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def __enter__(self) -> Path:
        (self.root / "tmp").mkdir(parents=True, exist_ok=True)
        (self.root / "06. Playbooks").mkdir(parents=True, exist_ok=True)
        (self.root / "06. Playbooks/Promotion Review Queue.md").write_text(PROMOTION_QUEUE, encoding="utf-8")
        write_json(self.root / "tmp/breadth-state.json", {
            "generated_at_utc": "2026-05-10T17:49:47Z",
            "status": "ok",
            "last_trading_day": "2026-05-08",
            "data": {"sector_participation": {"sectors": [
                {"ticker": ticker, "label": label, "sma_50": 50, "above_50dma": ticker not in {"XLE", "XLU"}, "as_of": "2026-05-08"}
                for ticker, label in seb.SECTOR_ETFS.items()
            ]}},
        })
        write_json(self.root / "tmp/market-state.json", {"generated_at_utc": "2026-05-10T17:49:56Z", "status": "ok", "last_trading_day": "2026-05-08"})
        write_json(self.root / "tmp/portfolio-config.json", {
            "generated_at_utc": "2026-05-07T22:14:01Z",
            "portfolio": {"cash": 10, "core": [], "tactical": [], "speculative": []},
            "tracked_universe": {
                "LLY": {"sector": "Healthcare", "coverage_tier": "watch", "portfolio_role": "watch_only", "workflow_state": "WATCH"},
                "CAT": {"sector": "Industrials", "coverage_tier": "watch", "portfolio_role": "tactical", "workflow_state": "WATCH"},
                "GS": {"sector": "Financials", "coverage_tier": "daily", "portfolio_role": "tactical", "workflow_state": "ALMOST"},
                "NVDA": {"sector": "Tech", "coverage_tier": "daily", "portfolio_role": "tactical", "workflow_state": "BLOCKED"},
                "JPM": {"sector": "Financials", "coverage_tier": "daily", "portfolio_role": "core", "workflow_state": "ALMOST"},
                "ETN": {"sector": "Industrials", "coverage_tier": "daily", "portfolio_role": "tactical", "workflow_state": "ALMOST"},
            },
        })
        write_json(self.root / "tmp/sector-correlation-check.json", {
            "generated_at_utc": "2026-05-10T17:55:04Z",
            "status": "ok",
            "source_quality": {"trust_level": "clean", "issues": []},
            "portfolio_exposure": {
                "sectors": [
                    {"sector": "Technology", "tickers": ["NVDA"], "draft_weight_pct": 25, "risk_cap_pct": 25, "distance_to_cap_pct": 0, "status": "at_cap"},
                    {"sector": "Financials", "tickers": ["JPM", "GS"], "draft_weight_pct": 21, "risk_cap_pct": 25, "distance_to_cap_pct": 4, "status": "near_cap"},
                    {"sector": "Industrials", "tickers": ["ETN"], "draft_weight_pct": 7, "risk_cap_pct": 25, "distance_to_cap_pct": 18, "status": "within_limit"},
                ],
                "correlated_sleeves": [{"sleeve": "Tech + AI-power", "status": "warning", "reason": "Direct Technology is at cap at 25% vs 25% cap; AI-power correlated sleeve is 32% including ETN."}],
            },
        })
        self.previous_workspace = seb.WORKSPACE
        self.previous_tmp = seb.TMP
        seb.WORKSPACE = self.root
        seb.TMP = self.root / "tmp"
        return self.root

    def __exit__(self, exc_type, exc, tb) -> None:
        seb.WORKSPACE = self.previous_workspace
        seb.TMP = self.previous_tmp
        self.tmp.cleanup()


class SectorExpansionBoardTests(unittest.TestCase):
    def test_all_11_sectors_question_authority_and_promotion_rows(self):
        with TempWorkspace():
            board = seb.build_board("post-close", fetcher_for(fake_histories()))
        self.assertEqual(board["status_question"], seb.QUESTION)
        self.assertEqual(len(board["sectors"]), 11)
        self.assertEqual([s["ticker"] for s in board["sectors"]], list(seb.SECTOR_ETFS.keys()))
        self.assertTrue(all(value is False for value in board["authority"].values()))
        promo = set(board["summary"]["promotion_review_candidates"])
        self.assertTrue({"LLY", "CAT", "GS", "NVDA"}.issubset(promo))
        self.assertNotIn("ETN", promo)
        self.assertNotIn("JPM", promo)
        self.assertIn("ETN", board["summary"]["approved_promotion_names"])
        self.assertIn("JPM", board["summary"]["approved_promotion_names"])
        tech = next(s for s in board["sectors"] if s["ticker"] == "XLK")
        self.assertEqual(tech["portfolio_exposure"]["status"], "at_cap")
        self.assertTrue(any("AI-power" in warning for warning in tech["warnings"]))
        short_ma = tech["short_term_moving_averages"]
        self.assertIn(short_ma["signal"], {"short_term_confirmed", "constructive_pullback", "momentum_cooling", "short_term_repair_needed", "mixed"})
        self.assertIsNotNone(short_ma["sma_5"])
        self.assertIsNotNone(short_ma["sma_20"])
        self.assertIn("subordinate", short_ma["warning"].lower())

    def test_underexposed_improving_healthcare_is_visible_owner_gated(self):
        with TempWorkspace():
            board = seb.build_board("post-close", fetcher_for(fake_histories()))
        healthcare = next(s for s in board["sectors"] if s["ticker"] == "XLV")
        self.assertTrue(healthcare["underexposed"])
        self.assertEqual(healthcare["leadership_status"], "improving_leadership")
        self.assertIn("Underexposed improving sector", healthcare["owner_gated_next_review_action"])
        self.assertEqual(healthcare["promotion_review_status"][0]["candidate"], "LLY")
        self.assertFalse(healthcare["promotion_review_status"][0]["owner_approval_granted"])

    def test_missing_spy_blocks(self):
        data = fake_histories()
        data.pop("SPY")
        with TempWorkspace():
            board = seb.build_board("post-close", fetcher_for(data))
        self.assertEqual(board["status"], "blocked")
        self.assertTrue(any("SPY" in err for err in board["errors"]))

    def test_partial_sector_data_degrades_not_clean(self):
        data = fake_histories()
        data.pop("XLC")
        with TempWorkspace():
            board = seb.build_board("post-close", fetcher_for(data))
        self.assertEqual(board["status"], "degraded")
        xlc = next(s for s in board["sectors"] if s["ticker"] == "XLC")
        self.assertEqual(xlc["status"], "missing_price_data")
        self.assertEqual(xlc["short_term_moving_averages"]["signal"], "unknown")

    def test_live_smoke_when_workspace_artifacts_exist(self):
        live_root = Path(__file__).resolve().parents[1]
        required = [live_root / "tmp/portfolio-config.json", live_root / "tmp/breadth-state.json", live_root / "tmp/sector-correlation-check.json"]
        if not all(path.exists() for path in required):
            self.skipTest("live workspace artifacts are not present")
        previous_workspace = seb.WORKSPACE
        previous_tmp = seb.TMP
        try:
            seb.WORKSPACE = live_root
            seb.TMP = live_root / "tmp"
            board = seb.build_board("post-close")
        finally:
            seb.WORKSPACE = previous_workspace
            seb.TMP = previous_tmp
        self.assertEqual(board["consumer_posture"], "review_only")
        self.assertEqual(len(board["sectors"]), 11)
        self.assertFalse(board["authority"]["portfolio_mutation_allowed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
