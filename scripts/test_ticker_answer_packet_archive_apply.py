from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ticker_answer_packet_archive_apply.py"

spec = importlib.util.spec_from_file_location("ticker_answer_packet_archive_apply", SCRIPT)
assert spec and spec.loader
archive_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive_module)


def test_archive_apply_guard_blocks_overwrite_conflicts() -> None:
    report = archive_module.build_report(apply=False, approval_reference=None)
    assert report["authority_boundary"]["overwrite_allowed"] is False
    assert report["authority_boundary"]["delete_allowed"] is False
    assert report["authority_boundary"]["capital_deployment_allowed"] is False
    assert report["authority_boundary"]["paper_or_live_execution_allowed"] is False
    assert report["summary"]["candidate_count"] == 42
    assert report["summary"]["overwrite_performed"] is False
    assert report["summary"]["delete_performed"] is False
    assert report["status"] in {"ready_to_apply", "already_archived", "blocked"}
    if report["summary"]["destination_hash_conflict_count"]:
        assert report["status"] == "blocked"
        assert "archive_destination_hash_conflicts_present" in report["validation"]["errors"]


def test_archive_apply_requires_approval_reference_when_apply_requested() -> None:
    report = archive_module.build_report(apply=True, approval_reference=None)
    assert report["apply_requested"] is True
    assert report["apply_performed"] is False
    assert "apply_requires_approval_reference" in report["validation"]["errors"]


def test_archive_apply_supports_versioned_root_without_overwrite() -> None:
    versioned_root = ROOT / "09. Archive" / "WF85 Legacy Ticker Answer Packets" / "versioned" / "legacy-42-regenerated-20260620"
    report = archive_module.build_report(
        apply=False,
        approval_reference=None,
        archive_root=versioned_root,
    )
    assert report["archive_root"].endswith("versioned/legacy-42-regenerated-20260620")
    assert report["summary"]["candidate_count"] == 42
    assert report["summary"]["destination_hash_conflict_count"] == 0
    assert report["summary"]["overwrite_performed"] is False
    assert report["summary"]["delete_performed"] is False
    assert report["status"] in {"ready_to_apply", "already_archived"}
    if report["status"] == "ready_to_apply":
        assert report["summary"]["move_ready_count"] == 42
    else:
        assert report["summary"]["already_archived_count"] == 42


if __name__ == "__main__":
    test_archive_apply_guard_blocks_overwrite_conflicts()
    test_archive_apply_requires_approval_reference_when_apply_requested()
    test_archive_apply_supports_versioned_root_without_overwrite()
