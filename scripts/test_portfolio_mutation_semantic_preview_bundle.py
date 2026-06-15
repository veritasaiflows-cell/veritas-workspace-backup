from __future__ import annotations

from pathlib import Path

import portfolio_mutation_semantic_preview_bundle as bundle

ROOT = Path(__file__).resolve().parents[1]


def test_semantic_preview_bundle_all_supported_categories() -> None:
    report = bundle.build_bundle("ETN", list(bundle.CATEGORIES), write_material=False)
    assert report["status"] == "ok"
    assert report["authority"]["preview_only"] is True
    assert report["authority"]["owner_file_write_allowed_by_bundle"] is False
    assert report["authority"]["trade_or_account_action_allowed"] is False
    assert report["summary"]["categories_requested"] == 6
    assert report["summary"]["categories_ok"] == 6
    categories = {row["category"] for row in report["categories"]}
    assert categories == set(bundle.CATEGORIES)
    for row in report["categories"]:
        assert row["status"] in {"ok", "already_current"}
        assert row["critical"] == 0
        assert row["writes_performed"] is False
        if row["status"] == "ok":
            assert row["target_file"] in {"03. Portfolio/Execution Board.md", "03. Portfolio/Portfolio Snapshot.md"}


if __name__ == "__main__":
    test_semantic_preview_bundle_all_supported_categories()
    print("portfolio_mutation_semantic_preview_bundle_tests_passed")
