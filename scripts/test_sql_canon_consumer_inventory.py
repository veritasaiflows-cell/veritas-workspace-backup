from __future__ import annotations

from pathlib import Path

import sql_canon_consumer_inventory as inventory


def test_generated_dirs_are_excluded() -> None:
    for name in ("graphify-out", "node_modules", "__pycache__", "dist", "build"):
        assert inventory.is_excluded(Path("scripts") / name / "thing.py")


def test_nested_generated_dirs_are_excluded() -> None:
    assert inventory.is_excluded(Path("scripts/graphify-out/cache/deep/stat-index.json"))


def test_real_consumers_are_not_excluded() -> None:
    assert not inventory.is_excluded(Path("scripts/finance_intelligence_state.py"))
    assert not inventory.is_excluded(Path("apps/pm-control-cockpit/src/server.ts"))
    assert not inventory.is_excluded(Path("state/cron-contracts/wf85.json"))


def test_similar_names_are_not_excluded() -> None:
    assert not inventory.is_excluded(Path("scripts/graphify_out_reader.py"))
    assert not inventory.is_excluded(Path("scripts/distribution_helper.py"))


def test_iter_files_yields_no_generated_paths() -> None:
    for path in inventory.iter_files():
        assert not inventory.is_excluded(path), path
