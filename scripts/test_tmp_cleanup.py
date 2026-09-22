from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import tmp_cleanup


def test_tmp_cleanup_dry_run_records_protection_assertions(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    tmp = workspace / "tmp"
    archive = workspace / "09. Archive" / "Scripts and Tmp Cleanup - Archived"
    tmp.mkdir(parents=True)
    archive.mkdir(parents=True)

    candidate = tmp / "old-scratch.json"
    candidate.write_text('{"ok": true}', encoding="utf-8")
    protected = tmp / "band-proposals.json"
    protected.write_text('{"protected": true}', encoding="utf-8")
    old = time.time() - 10 * 24 * 60 * 60
    os.utime(candidate, (old, old))
    os.utime(protected, (old, old))

    monkeypatch.setattr(tmp_cleanup, "WORKSPACE", workspace)
    monkeypatch.setattr(tmp_cleanup, "TMP", tmp)
    monkeypatch.setattr(tmp_cleanup, "ARCHIVE_ROOT", archive)
    monkeypatch.setattr(tmp_cleanup, "OUT_PATH", tmp / "tmp-cleanup-report.json")
    monkeypatch.setattr(sys, "argv", ["tmp_cleanup.py", "--dry-run", "--days", "7"])

    assert tmp_cleanup.main() == 0
    report = json.loads((tmp / "tmp-cleanup-report.json").read_text(encoding="utf-8"))

    assert report["status"] == "ok"
    assert report["operator_action"] == "NO_REPLY"
    assert report["validation"] == {"status": "ok", "errors": [], "warnings": []}
    assert report["mode"] == "dry-run"
    assert report["summary"]["eligible_count"] == 1
    assert report["summary"]["moved_count"] == 0
    assert len(report["summary"]["candidate_digest"]) == 64
    assert report["summary"]["protected_violation_count"] == 0
    assert report["protection_assertions"]["all_candidates_pass_protection_filter"] is True
    assert report["protection_assertions"]["dry_run_no_delete_assertion"] is True
    assert report["protection_assertions"]["destructive_cleanup_requires_separate_owner_approval"] is True
    assert report["authority_boundary"]["review_only_dry_run"] is True
    assert report["authority_boundary"]["archive_move_allowed"] is False
    assert report["authority_boundary"]["delete_allowed"] is False
    assert report["authority_boundary"]["cron_schedule_mutation_allowed"] is False
    assert report["authority_boundary"]["runtime_config_mutation_allowed"] is False
    assert report["authority_boundary"]["finance_canon_mutation_allowed"] is False
    assert report["authority_boundary"]["portfolio_mutation_allowed"] is False
    assert report["authority_boundary"]["paper_or_live_execution_allowed"] is False
    assert report["authority_boundary"]["brokerage_or_account_action_allowed"] is False
    assert report["authority_boundary"]["owner_approval_inferred"] is False
    assert report["candidates"][0]["path"] == "tmp/old-scratch.json"
    assert protected.exists()
    assert candidate.exists()


def _naive_newest_mtime(path: Path):
    from datetime import datetime, timezone

    if path.is_file():
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    mtimes = [datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc) for p in path.rglob("*") if p.exists()]
    mtimes.append(datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc))
    return max(mtimes)


def test_scan_matches_naive_mtime(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "tmp" / "bigdir"
    (target / "sub" / "deep").mkdir(parents=True)
    (target / "a.txt").write_text("a" * 100, encoding="utf-8")
    (target / "sub" / "b.bin").write_bytes(bytes(range(256)) * 40)
    (target / "sub" / "deep" / "c.md").write_text("# c", encoding="utf-8")
    old = time.time() - 3 * 24 * 60 * 60
    os.utime(target / "sub" / "b.bin", (old, old))
    monkeypatch.setattr(tmp_cleanup, "WORKSPACE", workspace)
    assert tmp_cleanup.newest_mtime(target) == _naive_newest_mtime(target)
    # Memoized second call returns the same object without retraversal.
    assert tmp_cleanup.scan_candidate(str(target)) is tmp_cleanup.scan_candidate(str(target))


def test_hash_cache_preserves_digest(tmp_path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    tmp = workspace / "tmp"
    archive = workspace / "09. Archive" / "Scripts and Tmp Cleanup - Archived"
    tmp.mkdir(parents=True)
    archive.mkdir(parents=True)
    candidate = tmp / "old-scratch.json"
    candidate.write_text('{"ok": true}', encoding="utf-8")
    old = time.time() - 10 * 24 * 60 * 60
    os.utime(candidate, (old, old))
    monkeypatch.setattr(tmp_cleanup, "WORKSPACE", workspace)
    monkeypatch.setattr(tmp_cleanup, "TMP", tmp)
    monkeypatch.setattr(tmp_cleanup, "ARCHIVE_ROOT", archive)
    monkeypatch.setattr(tmp_cleanup, "OUT_PATH", tmp / "tmp-cleanup-report.json")
    monkeypatch.setattr(sys, "argv", ["tmp_cleanup.py", "--dry-run", "--days", "7"])
    assert tmp_cleanup.main() == 0
    first = json.loads((tmp / "tmp-cleanup-report.json").read_text(encoding="utf-8"))
    cache_file = workspace / "state" / "tmp-cleanup-hash-cache.json"
    assert cache_file.exists()
    assert tmp_cleanup.main() == 0
    second = json.loads((tmp / "tmp-cleanup-report.json").read_text(encoding="utf-8"))
    assert second["summary"]["candidate_digest"] == first["summary"]["candidate_digest"]
    assert second["candidates"] == first["candidates"]
    assert second["validation"] == {"status": "ok", "errors": [], "warnings": []}
