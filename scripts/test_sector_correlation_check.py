#!/usr/bin/env python3
"""Targeted WF53 tests for the standalone sector correlation producer."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sector_correlation_check as scc


RISK_RULES = """# Risk Rules

- Normal max single position: 15%
- Max single sector: 25%
- Do not exceed 10% total in the speculative sleeve without an explicit written exception
"""

PORTFOLIO_SNAPSHOT = """# Portfolio Snapshot

## Sector allocation vs. Risk Rules caps

| Sector | Names | Draft Weight Total | Risk Rules Cap | Status |
|---|---|---|---|---|
| Technology | MSFT (10%) + GOOG (10%) + NVDA (5%) | **25%** | 25% | AT CAP |
| Financials | JPM (14%) + GS (7%) | 21% | 25% | Within limit |
| Industrials | ETN (7%) | 7% | 25% | Within limit |
| Cash | — | 10% | — | Aligned |
"""

WATCHLIST = """# Coverage and Watchlist

| Ticker | Sector | Coverage Tier | Thesis pointer | Deployment/action pointer | Source lineage |
|---|---|---|---|---|---|
| LLY | Healthcare | Sector monitor | thesis section | Execution Board pointer | Technical lineage |
| CAT | Industrials | Tactical | thesis section | Execution Board pointer | Technical lineage |
"""


def base_config() -> dict:
    return {
        "generated_at_utc": "2026-05-07T22:14:01Z",
        "portfolio": {
            "cash": 10,
            "core": [
                {"ticker": "MSFT", "weight": 10, "sector": "Tech"},
                {"ticker": "JPM", "weight": 14, "sector": "Financials"},
                {"ticker": "GOOG", "weight": 10, "sector": "Tech"},
            ],
            "tactical": [
                {"ticker": "ETN", "weight": 7, "sector": "Industrials"},
                {"ticker": "NVDA", "weight": 5, "sector": "Tech"},
                {"ticker": "GS", "weight": 7, "sector": "Financials"},
            ],
            "speculative": [],
        },
        "tracked_universe": {
            "GS": {"sector": "Financials", "portfolio_role": "tactical", "workflow_state": "ALMOST", "coverage_lane": "execution"},
            "LLY": {"sector": "Healthcare", "portfolio_role": "watch_only", "workflow_state": "WATCH", "coverage_lane": "watch"},
            "CAT": {"sector": "Industrials", "portfolio_role": "tactical", "workflow_state": "WATCH", "coverage_lane": "watch"},
            "VRT": {"sector": "Industrials", "portfolio_role": "watch_only", "workflow_state": "WATCH", "coverage_lane": "execution"},
        },
        "risk_thresholds": {"max_sector_pct": 25, "max_single_position_normal": 15},
    }


def base_daily() -> dict:
    return {
        "generated_at_utc": "2026-05-10T17:55:04Z",
        "consumer_posture": "review_only",
        "canonical_mutation_allowed": False,
        "portfolio_mutation_allowed": False,
        "deployment_state_mutation_allowed": False,
        "trade_execution_allowed": False,
        "owner_approval_granted": False,
        "source_freshness": {
            "overall_classification": "fresh",
            "trust_level": "clean",
            "stop_line": False,
            "capital_action_allowed": False,
        },
    }


class TempWorkspace:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def __enter__(self) -> Path:
        for rel in ["tmp", "07. Risk", "03. Portfolio", "02. Markets"]:
            (self.root / rel).mkdir(parents=True, exist_ok=True)
        (self.root / "07. Risk/Risk Rules.md").write_text(RISK_RULES, encoding="utf-8")
        (self.root / "03. Portfolio/Portfolio Snapshot.md").write_text(PORTFOLIO_SNAPSHOT, encoding="utf-8")
        (self.root / "04. Research/Coverage and Watchlist.md").write_text(WATCHLIST, encoding="utf-8")
        write_json(self.root / "tmp/portfolio-config.json", base_config())
        write_json(self.root / "tmp/deployment-readiness-surface.json", {"generated_at_utc": "2026-05-10T17:55:04Z", "system": {"canonical_note_mutation_allowed": False, "stop_line": False}})
        write_json(self.root / "tmp/trigger-sheet.json", {"generated_at_utc": "2026-05-10T17:50:09Z", "last_trading_day": "2026-05-08"})
        write_json(self.root / "tmp/band-proposals.json", {"generated_at_utc": "2026-05-10T17:50:02Z", "status": "ok"})
        write_json(self.root / "tmp/daily-review-objects-post-close.json", base_daily())
        self.previous = scc.WORKSPACE
        scc.WORKSPACE = self.root
        return self.root

    def __exit__(self, exc_type, exc, tb) -> None:
        scc.WORKSPACE = self.previous
        self.tmp.cleanup()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class SectorCorrelationCheckTests(unittest.TestCase):
    def test_technology_at_cap_and_ai_power_warning(self):
        with TempWorkspace():
            artifact = scc.build_artifact("post-close")
        tech = next(sector for sector in artifact["portfolio_exposure"]["sectors"] if sector["sector"] == "Technology")
        sleeve = artifact["portfolio_exposure"]["correlated_sleeves"][0]
        self.assertEqual(artifact["status"], "ok")
        self.assertEqual(tech["draft_weight_pct"], 25)
        self.assertEqual(tech["status"], "at_cap")
        self.assertEqual(sleeve["sleeve"], "Tech + AI-power")
        self.assertEqual(sleeve["draft_weight_pct"], 32)
        self.assertEqual(sleeve["status"], "warning")
        self.assertIn("ETN", sleeve["included_non_sector_tickers"])

    def test_watch_names_remain_review_only_and_not_promotion_eligible(self):
        with TempWorkspace():
            artifact = scc.build_artifact("post-close")
        by_ticker = {item["ticker"]: item for item in artifact["tracked_universe_context"]}
        self.assertFalse(by_ticker["LLY"]["eligible_for_promotion"])
        self.assertFalse(by_ticker["CAT"]["eligible_for_promotion"])
        self.assertEqual(by_ticker["LLY"]["candidate_role"], "diversification_watch")
        for item in artifact["promotion_impact_checks"]:
            self.assertFalse(item["eligible_for_promotion"])
            self.assertEqual(item["authority"]["portfolio_mutation_allowed"], False)

    def test_gs_financials_stays_inside_cap_but_owner_gated(self):
        with TempWorkspace():
            artifact = scc.build_artifact("post-close")
        gs = next(item for item in artifact["promotion_impact_checks"] if item["ticker"] == "GS")
        self.assertEqual(gs["current_sector_weight_pct"], 21)
        self.assertEqual(gs["pro_forma_sector_weight_pct"], 21)
        self.assertEqual(gs["cap_status_after"], "near_cap")
        self.assertIn("owner", gs["review_only_verdict"])

    def test_missing_sector_cap_fails_closed(self):
        with TempWorkspace() as root:
            (root / "07. Risk/Risk Rules.md").write_text("# Risk Rules\n", encoding="utf-8")
            cfg = base_config()
            cfg["risk_thresholds"].pop("max_sector_pct")
            write_json(root / "tmp/portfolio-config.json", cfg)
            artifact = scc.build_artifact("post-close")
        self.assertEqual(artifact["status"], "blocked")
        self.assertTrue(any("max single sector" in err.lower() for err in artifact["errors"]))

    def test_missing_weights_fails_closed(self):
        with TempWorkspace() as root:
            cfg = base_config()
            cfg["portfolio"] = {"cash": 10, "core": [], "tactical": [], "speculative": []}
            write_json(root / "tmp/portfolio-config.json", cfg)
            artifact = scc.build_artifact("post-close")
        self.assertEqual(artifact["status"], "blocked")
        self.assertTrue(any("model weights" in err.lower() for err in artifact["errors"]))

    def test_partial_generated_artifacts_degrade_but_keep_exposure_math(self):
        with TempWorkspace() as root:
            daily = base_daily()
            daily["source_freshness"] = {"overall_classification": "partial", "trust_level": "review_required", "stop_line": False}
            write_json(root / "tmp/daily-review-objects-post-close.json", daily)
            write_json(root / "tmp/band-proposals.json", {"generated_at_utc": "2026-05-10T17:50:02Z", "status": "needs_review"})
            artifact = scc.build_artifact("post-close")
        tech = next(sector for sector in artifact["portfolio_exposure"]["sectors"] if sector["sector"] == "Technology")
        self.assertEqual(artifact["status"], "degraded")
        self.assertEqual(artifact["source_quality"]["trust_level"], "review_required")
        self.assertEqual(tech["draft_weight_pct"], 25)

    def test_authority_flags_enforced_false_and_true_source_blocks(self):
        with TempWorkspace() as root:
            daily = base_daily()
            daily["trade_execution_allowed"] = True
            write_json(root / "tmp/daily-review-objects-post-close.json", daily)
            artifact = scc.build_artifact("post-close")
        self.assertEqual(artifact["status"], "blocked")
        for value in artifact["authority"].values():
            self.assertIs(value, False)

    def test_no_forbidden_outcome_language_except_authority_flag_name(self):
        with TempWorkspace():
            artifact = scc.build_artifact("post-close")
        text = json.dumps(artifact).lower().replace("probability_or_modeling_authority", "")
        for forbidden in ["expected return", "win rate", "calibrated", "predictive"]:
            self.assertNotIn(forbidden, text)

    def test_live_smoke_when_workspace_artifacts_exist(self):
        live_root = Path(__file__).resolve().parents[1]
        required = [live_root / rel for rel in [
            "tmp/portfolio-config.json",
            "07. Risk/Risk Rules.md",
            "03. Portfolio/Portfolio Snapshot.md",
        ]]
        if not all(path.exists() for path in required):
            self.skipTest("live workspace artifacts are not present")
        previous = scc.WORKSPACE
        try:
            scc.WORKSPACE = live_root
            artifact = scc.build_artifact("post-close")
        finally:
            scc.WORKSPACE = previous
        self.assertEqual(artifact["consumer_posture"], "review_only")
        self.assertFalse(artifact["authority"]["portfolio_mutation_allowed"])
        self.assertTrue(any(sec["sector"] == "Technology" for sec in artifact["portfolio_exposure"]["sectors"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
