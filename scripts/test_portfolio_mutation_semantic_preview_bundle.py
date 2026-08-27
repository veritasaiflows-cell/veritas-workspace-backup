from __future__ import annotations

import json
from pathlib import Path

import portfolio_mutation_semantic_preview_bundle as bundle

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "tmp" / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"


def current_proposal_ticker() -> str:
    payload = json.loads(BUNDLE.read_text(encoding="utf-8"))
    for packet in payload.get("proposals") or []:
        ticker = str(packet.get("ticker_or_scope") or packet.get("ticker") or "").upper()
        if ticker:
            return ticker
    raise AssertionError("current proposal ticker not found")


def test_semantic_preview_bundle_all_supported_categories() -> None:
    current_categories = [category for category in bundle.CATEGORIES if category != "earnings_state"]
    report = bundle.build_bundle(current_proposal_ticker(), current_categories, write_material=False)
    assert report["status"] == "ok"
    assert report["authority"]["preview_only"] is True
    assert report["authority"]["owner_file_write_allowed_by_bundle"] is False
    assert report["authority"]["trade_or_account_action_allowed"] is False
    assert report["summary"]["categories_requested"] == len(current_categories)
    assert report["summary"]["categories_ok"] == len(current_categories)
    categories = {row["category"] for row in report["categories"]}
    assert categories == set(current_categories)
    for row in report["categories"]:
        assert row["status"] in {"ok", "already_current"}
        assert row["critical"] == 0
        assert row["writes_performed"] is False
        if row["status"] == "ok":
            assert row["target_file"] in {"03. Portfolio/Execution Board.md", "03. Portfolio/Portfolio Snapshot.md"}


if __name__ == "__main__":
    test_semantic_preview_bundle_all_supported_categories()
    print("portfolio_mutation_semantic_preview_bundle_tests_passed")
