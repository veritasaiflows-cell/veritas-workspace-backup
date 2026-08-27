from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APPLY_SCRIPT = ROOT / "scripts" / "backup_rollback_delete_apply.py"
PACKET_SCRIPT = ROOT / "scripts" / "backup_rollback_delete_prep_packet.py"


def load_module(path: Path, name: str):
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed_workspace(root: Path) -> dict:
    rollback = root / "state" / "tmp-lifecycle-rollback" / "cleanup"
    rollback.mkdir(parents=True)
    (rollback / "one.txt").write_text("rollback", encoding="utf-8")
    backups = root / "backups" / "finance"
    backups.mkdir(parents=True)
    (backups / "keep.sqlite").write_bytes(b"not a real db for this test")
    tmp = root / "tmp"
    tmp.mkdir(parents=True)
    (tmp / "db-lifecycle-manifest.json").write_text(
        json.dumps({"status": "validation_error", "summary": {"delete_ready_count": 0}}),
        encoding="utf-8",
    )
    (root / "state" / "tmp-lifecycle-deletion-tombstone.json").write_text(
        json.dumps({"schema_version": 1, "deleted_records": [], "runs": [], "events": []}),
        encoding="utf-8",
    )
    prep = load_module(PACKET_SCRIPT, "backup_rollback_delete_prep_packet")
    return prep.build_packet(workspace_root=root, generated_at_utc="2026-07-05T23:30:00Z", include_sqlite_checks=False)


def test_dry_run_validates_without_deleting() -> None:
    apply = load_module(APPLY_SCRIPT, "backup_rollback_delete_apply")
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        packet = seed_workspace(workspace)
        packet_path = workspace / "tmp" / "packet.json"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        phrase = packet["rollback_delete_microbatch"]["approval_phrase"]

        report = apply.build_report(
            packet_path=packet_path,
            approval_phrase=phrase,
            dry_run=True,
            workspace_root=workspace,
        )

        assert report["validation"]["status"] == "ok"
        assert report["summary"]["dry_run"] is True
        assert report["summary"]["delete_performed"] is False
        assert (workspace / "state" / "tmp-lifecycle-rollback" / "cleanup" / "one.txt").exists()
        assert (workspace / "backups" / "finance" / "keep.sqlite").exists()


def test_apply_deletes_only_rollback_rows() -> None:
    apply = load_module(APPLY_SCRIPT, "backup_rollback_delete_apply")
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        packet = seed_workspace(workspace)
        packet_path = workspace / "tmp" / "packet.json"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        phrase = packet["rollback_delete_microbatch"]["approval_phrase"]

        report = apply.build_report(
            packet_path=packet_path,
            approval_phrase=phrase,
            dry_run=False,
            workspace_root=workspace,
        )

        assert report["validation"]["status"] == "ok"
        assert report["summary"]["delete_performed"] is True
        assert not (workspace / "state" / "tmp-lifecycle-rollback" / "cleanup").exists()
        assert (workspace / "backups" / "finance" / "keep.sqlite").exists()


def test_apply_is_idempotent_when_target_already_missing() -> None:
    apply = load_module(APPLY_SCRIPT, "backup_rollback_delete_apply")
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        packet = seed_workspace(workspace)
        packet_path = workspace / "tmp" / "packet.json"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        phrase = packet["rollback_delete_microbatch"]["approval_phrase"]
        cleanup = workspace / "state" / "tmp-lifecycle-rollback" / "cleanup"

        for child in cleanup.iterdir():
            child.unlink()
        cleanup.rmdir()

        report = apply.build_report(
            packet_path=packet_path,
            approval_phrase=phrase,
            dry_run=False,
            workspace_root=workspace,
        )

        assert report["validation"]["status"] == "ok"
        assert report["summary"]["delete_performed"] is False
        assert report["results"][0]["already_missing"] is True
        assert (workspace / "backups" / "finance" / "keep.sqlite").exists()


def test_apply_retries_transient_tree_delete_failure() -> None:
    apply = load_module(APPLY_SCRIPT, "backup_rollback_delete_apply")
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        packet = seed_workspace(workspace)
        packet_path = workspace / "tmp" / "packet.json"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        phrase = packet["rollback_delete_microbatch"]["approval_phrase"]
        original_rmtree = apply.shutil.rmtree
        calls = {"count": 0}

        def flaky_rmtree(path, *args, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise OSError("directory not empty")
            return original_rmtree(path, *args, **kwargs)

        apply.shutil.rmtree = flaky_rmtree
        try:
            report = apply.build_report(
                packet_path=packet_path,
                approval_phrase=phrase,
                dry_run=False,
                workspace_root=workspace,
            )
        finally:
            apply.shutil.rmtree = original_rmtree

        assert calls["count"] >= 2
        assert report["validation"]["status"] == "ok"
        assert not (workspace / "state" / "tmp-lifecycle-rollback" / "cleanup").exists()


def test_apply_uses_manual_fallback_when_tree_delete_keeps_failing() -> None:
    apply = load_module(APPLY_SCRIPT, "backup_rollback_delete_apply")
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        packet = seed_workspace(workspace)
        packet_path = workspace / "tmp" / "packet.json"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
        phrase = packet["rollback_delete_microbatch"]["approval_phrase"]
        original_rmtree = apply.shutil.rmtree

        def failing_rmtree(path, *args, **kwargs):
            raise OSError("directory not empty")

        apply.shutil.rmtree = failing_rmtree
        try:
            report = apply.build_report(
                packet_path=packet_path,
                approval_phrase=phrase,
                dry_run=False,
                workspace_root=workspace,
            )
        finally:
            apply.shutil.rmtree = original_rmtree

        assert report["validation"]["status"] == "ok"
        assert not (workspace / "state" / "tmp-lifecycle-rollback" / "cleanup").exists()
        assert (workspace / "backups" / "finance" / "keep.sqlite").exists()


def test_wrong_approval_phrase_blocks() -> None:
    apply = load_module(APPLY_SCRIPT, "backup_rollback_delete_apply")
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        packet = seed_workspace(workspace)
        packet_path = workspace / "tmp" / "packet.json"
        packet_path.write_text(json.dumps(packet), encoding="utf-8")

        report = apply.build_report(
            packet_path=packet_path,
            approval_phrase="wrong",
            dry_run=False,
            workspace_root=workspace,
        )

        assert report["validation"]["status"] == "blocked"
        assert "approval_phrase_mismatch" in report["validation"]["errors"]
        assert (workspace / "state" / "tmp-lifecycle-rollback" / "cleanup").exists()


if __name__ == "__main__":
    test_dry_run_validates_without_deleting()
    test_apply_deletes_only_rollback_rows()
    test_apply_is_idempotent_when_target_already_missing()
    test_apply_retries_transient_tree_delete_failure()
    test_apply_uses_manual_fallback_when_tree_delete_keeps_failing()
    test_wrong_approval_phrase_blocks()
    print("backup rollback delete apply tests passed")
