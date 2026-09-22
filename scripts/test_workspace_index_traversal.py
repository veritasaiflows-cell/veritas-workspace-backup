"""Equivalence: pruned iter_markdown must yield exactly the naive filter set."""
from __future__ import annotations

import os
from pathlib import Path

import workspace_index


def naive_markdown(root: Path) -> set[str]:
    """Old filter-after-rglob oracle, kept verbatim in behavior."""
    found = set()
    for path in root.rglob("*.md"):
        rel_parts = path.relative_to(root).parts
        if any(part in workspace_index.EXCLUDED_DIRS for part in rel_parts):
            continue
        found.add(path.resolve().as_posix())
    return found


def build_tree(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "index.md").write_text("# root", encoding="utf-8")
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "a.md").write_text("# a", encoding="utf-8")
    (root / "notes" / "data.json").write_text("{}", encoding="utf-8")
    (root / "notes" / "deep" / "deeper").mkdir(parents=True)
    (root / "notes" / "deep" / "deeper" / "b.md").write_text("# b", encoding="utf-8")
    for excluded in (".git", "tmp", "backups", "__pycache__", ".openclaw"):
        target = root / "notes" / "deep" / excluded
        target.mkdir(parents=True)
        (target / "hidden.md").write_text("# hidden", encoding="utf-8")
        nested = target / "nested"
        nested.mkdir(parents=True)
        (nested / "hidden2.md").write_text("# hidden2", encoding="utf-8")
    top_excluded = root / "tmp"
    top_excluded.mkdir(parents=True)
    (top_excluded / "top.md").write_text("# top", encoding="utf-8")
    (root / "weird.tmp.md").write_text("# weird", encoding="utf-8")


def test_pruned_matches_naive_oracle(tmp_path) -> None:
    root = tmp_path / "ws"
    build_tree(root)
    expected = naive_markdown(root)
    actual = {p.resolve().as_posix() for p in workspace_index.iter_markdown(root)}
    assert actual == expected
    assert len(actual) == 4
    for excluded in (".git", "tmp", "backups", "__pycache__", ".openclaw"):
        assert not any(f"/{excluded}/" in item for item in actual)


def test_pruned_expected_members(tmp_path) -> None:
    root = tmp_path / "ws"
    build_tree(root)
    actual = {p.relative_to(root).as_posix() for p in workspace_index.iter_markdown(root)}
    assert actual == {"index.md", "notes/a.md", "notes/deep/deeper/b.md", "weird.tmp.md"}


def test_pruned_handles_symlink(tmp_path) -> None:
    root = tmp_path / "ws"
    build_tree(root)
    try:
        os.symlink(str(root / "notes" / "a.md"), str(root / "notes" / "link.md"))
    except (OSError, NotImplementedError):
        return
    expected = naive_markdown(root)
    actual = {p.resolve().as_posix() for p in workspace_index.iter_markdown(root)}
    assert actual == expected
