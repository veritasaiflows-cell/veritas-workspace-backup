from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "post_close_final_quote_ledger.py"

spec = importlib.util.spec_from_file_location("post_close_final_quote_ledger", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_tier_a_coverage_gate_fresh_quote_targets_are_deduped() -> None:
    with TemporaryDirectory() as tmpdir:
        gate_path = Path(tmpdir) / "tier-a-trade-grade-coverage-gate.json"
        gate_path.write_text(
            json.dumps(
                {
                    "cohorts": {
                        "finance_canon_tier_a": [
                            {"ticker": "bkng", "depth_blockers": ["fresh_quote_required"]},
                            {"ticker": "meta", "depth_blockers": ["other_blocker"]},
                        ],
                        "data_plane_tier_a": [
                            {"ticker": "BKNG", "depth_blockers": ["fresh_quote_required"]},
                            {"ticker": "RTX", "depth_blockers": ["fresh_quote_required", "other_blocker"]},
                        ],
                    }
                }
            ),
            encoding="utf-8",
        )

        original = module.TIER_A_COVERAGE_GATE
        try:
            module.TIER_A_COVERAGE_GATE = gate_path
            assert module.tier_a_coverage_gate_fresh_quote_targets() == ["BKNG", "RTX"]
        finally:
            module.TIER_A_COVERAGE_GATE = original


def test_missing_tier_a_coverage_gate_returns_no_targets() -> None:
    original = module.TIER_A_COVERAGE_GATE
    try:
        module.TIER_A_COVERAGE_GATE = ROOT / "tmp" / "missing-tier-a-gate.json"
        assert module.tier_a_coverage_gate_fresh_quote_targets() == []
    finally:
        module.TIER_A_COVERAGE_GATE = original


def test_tier_ab_stale_decision_card_price_targets_are_deduped() -> None:
    with TemporaryDirectory() as tmpdir:
        cards_path = Path(tmpdir) / "trade-grade-decision-cards.json"
        cards_path.write_text(
            json.dumps(
                {
                    "cards": [
                        {
                            "ticker": "RTX",
                            "auto_tier": "Tier A",
                            "current_price": {"market_date": "2026-06-24"},
                        },
                        {
                            "ticker": "xlb",
                            "auto_tier": "Tier B",
                            "current_price": {"market_date": "2026-06-23"},
                        },
                        {
                            "ticker": "XLB",
                            "auto_tier": "Tier B",
                            "current_price": {"market_date": "2026-06-23"},
                        },
                        {
                            "ticker": "THIN",
                            "auto_tier": "Tier C",
                            "current_price": {"market_date": "2026-06-23"},
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )

        original = module.TRADE_GRADE_DECISION_CARDS
        try:
            module.TRADE_GRADE_DECISION_CARDS = cards_path
            assert module.tier_ab_stale_decision_card_price_targets() == ["XLB"]
        finally:
            module.TRADE_GRADE_DECISION_CARDS = original


if __name__ == "__main__":
    test_tier_a_coverage_gate_fresh_quote_targets_are_deduped()
    test_missing_tier_a_coverage_gate_returns_no_targets()
    test_tier_ab_stale_decision_card_price_targets_are_deduped()
    print("ok")
