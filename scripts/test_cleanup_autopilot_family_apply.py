from __future__ import annotations

import json
import tempfile
from pathlib import Path

import cleanup_autopilot_family_apply as apply_script
import cleanup_autopilot_family_packets as packet_script


def seed_workspace(root: Path, *, approval_ready: bool = True) -> tuple[list[Path], str]:
    apply_script.ROOT = root
    apply_script.TMP = root / "tmp"
    apply_script.PACKET = apply_script.TMP / "cleanup-autopilot-family-packets.json"
    apply_script.APPLY_REPORT = apply_script.TMP / "cleanup-autopilot-family-apply-report.json"
    apply_script.ROLLBACK_ROOT = root / "state" / "tmp-lifecycle-rollback" / "cleanup-autopilot-family"

    target_dir = root / "tmp" / "go-bin-backup-20260607"
    target_dir.mkdir(parents=True)
    files = [target_dir / "a.exe", target_dir / "b.exe"]
    files[0].write_text("aaa", encoding="utf-8")
    files[1].write_text("bbb", encoding="utf-8")
    records = [
        {
            "path": file.relative_to(root).as_posix(),
            "bytes": file.stat().st_size,
            "last_write_utc": "2026-01-01T00:00:00Z",
            "sha256": apply_script.file_sha256(file),
        }
        for file in files
    ]
    digest = packet_script.inventory_digest(records)
    phrase = (
        "Approve Cleanup Autopilot go_binary_backup_cache microbatch "
        f"{digest} exactly as listed in tmp/cleanup-autopilot-family-packets.json."
    )
    family = {
        "family_id": "go_binary_backup_cache",
        "readiness_state": "owner_ready_backup_only_after_exact_phrase",
        "delete_allowed_now": False,
        "approval_ready_after_owner_phrase": approval_ready,
        "bytes": sum(record["bytes"] for record in records),
        "inventory_digest": digest,
        "reference_check": {
            "status": "historical_references_only",
            "active_hit_path_count": 0,
        },
        "records": records,
        "record_manifest": {
            "complete_manifest_in_packet": True,
            "content_sha256_included": True,
        },
        "approval_surface": {
            "approval_phrase": phrase,
        },
    }
    apply_script.PACKET.write_text(json.dumps({"families": [family]}), encoding="utf-8")
    return files, phrase


def test_family_dry_run_does_not_delete() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        files, phrase = seed_workspace(Path(tmpdir))
        report = apply_script.build_report(family_id="go_binary_backup_cache", apply=False, approval_phrase=phrase)
        assert report["validation"]["status"] == "ok"
        assert report["status"] == "dry_run_ok"
        assert all(file.exists() for file in files)


def test_family_dry_run_accepts_zero_byte_records() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        files, phrase = seed_workspace(root)
        zero_file = root / "tmp" / "go-bin-backup-20260607" / "empty.pb"
        zero_file.write_bytes(b"")
        zero_record = {
            "path": zero_file.relative_to(root).as_posix(),
            "bytes": 0,
            "last_write_utc": "2026-01-01T00:00:00Z",
            "sha256": apply_script.file_sha256(zero_file),
        }
        packet = json.loads(apply_script.PACKET.read_text(encoding="utf-8"))
        packet["families"][0]["records"] = [zero_record]
        packet["families"][0]["bytes"] = 0
        apply_script.PACKET.write_text(json.dumps(packet), encoding="utf-8")

        report = apply_script.build_report(family_id="go_binary_backup_cache", apply=False, approval_phrase=phrase)

        assert report["validation"]["status"] == "ok"
        assert report["status"] == "dry_run_ok"
        assert zero_file.exists()
        assert all(file.exists() for file in files)


def test_family_apply_requires_exact_phrase() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        files, _phrase = seed_workspace(Path(tmpdir))
        report = apply_script.build_report(family_id="go_binary_backup_cache", apply=True, approval_phrase="wrong")
        assert report["validation"]["status"] == "blocked"
        assert "approval_phrase_mismatch" in report["validation"]["errors"]
        assert all(file.exists() for file in files)


def test_family_apply_deletes_after_rollback() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        files, phrase = seed_workspace(root)
        report = apply_script.build_report(family_id="go_binary_backup_cache", apply=True, approval_phrase=phrase)
        assert report["validation"]["status"] == "ok"
        assert report["summary"]["deleted_count"] == 2
        assert all(not file.exists() for file in files)
        for record in report["deleted_records"]:
            assert (root / record["rollback_copy"]).exists()


def test_family_not_ready_blocks_apply() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        files, phrase = seed_workspace(Path(tmpdir), approval_ready=False)
        report = apply_script.build_report(family_id="go_binary_backup_cache", apply=True, approval_phrase=phrase)
        assert report["validation"]["status"] == "blocked"
        assert any(error.startswith("family_not_approval_ready:") for error in report["validation"]["errors"])
        assert all(file.exists() for file in files)
