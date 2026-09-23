from __future__ import annotations

import re
from datetime import date

import archive_retention as ar


def _setup(tmp_path, monkeypatch, tracked: set[str], refs: dict[str, list[str]]):
    archive = tmp_path / "09. Archive"
    cleanup = archive / "Scripts and Tmp Cleanup - Archived"
    for name in ("2026-06-01-tmp-cleanup", "2026-09-20-tmp-cleanup", "2026-05-03-tmp-cleanup", "2026-06-02-tmp-cleanup"):
        (cleanup / name).mkdir(parents=True)
        (cleanup / name / "f.json").write_text("{}", encoding="utf-8")
    (archive / "skills-backup-20260601.zip").write_bytes(b"zip")
    (archive / "unrelated-folder").mkdir()
    monkeypatch.setattr(ar, "ROOT", tmp_path)
    monkeypatch.setattr(ar, "RULES", (
        (cleanup, re.compile(r"^(\d{4}-\d{2}-\d{2})-tmp-cleanup$")),
        (archive, re.compile(r"^skills-backup-(\d{4})(\d{2})(\d{2})\.zip$")),
    ))
    monkeypatch.setattr(ar, "tracked_count", lambda path: 5 if path.name in tracked else 0)
    monkeypatch.setattr(ar, "referenced_by", lambda name: refs.get(name, []))


def test_only_old_untracked_unreferenced_items_are_eligible(tmp_path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch, tracked={"2026-05-03-tmp-cleanup"}, refs={"2026-06-02-tmp-cleanup": ["scripts/x.py"]})
    rows = {row["path"].split("/")[-1]: row for row in ar.evaluate(30, date(2026, 9, 22))}
    assert rows["2026-06-01-tmp-cleanup"]["eligible"]
    assert rows["skills-backup-20260601.zip"]["eligible"]
    assert not rows["2026-09-20-tmp-cleanup"]["eligible"]  # too young
    assert not rows["2026-05-03-tmp-cleanup"]["eligible"]  # tracked by git
    assert not rows["2026-06-02-tmp-cleanup"]["eligible"]  # still referenced
    assert "unrelated-folder" not in rows
