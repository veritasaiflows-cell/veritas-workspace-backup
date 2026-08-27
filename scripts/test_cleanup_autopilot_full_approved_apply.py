from __future__ import annotations

import tempfile
from pathlib import Path

import cleanup_autopilot_full_approved_apply as apply_script


def configure_root(root: Path) -> None:
    apply_script.ROOT = root
    apply_script.TMP = root / "tmp"
    apply_script.ROLLBACK_ROOT = root / "state" / "tmp-lifecycle-rollback" / "cleanup-autopilot-full-approved"
    apply_script.OUT = root / "tmp" / "cleanup-autopilot-full-approved-apply-report.json"
    apply_script.OTEL_DIR = root / "tmp" / "otel-collector"
    apply_script.AUDIO_TOOLS_DIR = root / "tmp" / "audio-tools"
    apply_script.GO_PROFILE_DIR = root / "tmp" / "go-profile-binaries"


def seed_files(root: Path) -> dict[str, Path]:
    audio = root / "tmp" / "audio-tools" / "node_modules" / "dep" / "index.js"
    profile = root / "tmp" / "go-profile-binaries" / "probe.exe"
    audio.parent.mkdir(parents=True)
    profile.parent.mkdir(parents=True)
    audio.write_text("audio cache", encoding="utf-8")
    profile.write_bytes(b"profile binary")
    return {"audio": audio, "profile": profile}


def test_dry_run_does_not_move_files() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_root(root)
        files = seed_files(root)

        report = apply_script.build_report(target="all", apply=False, approval_note="approved")

        assert report["validation"]["status"] == "ok"
        assert report["status"] == "dry_run_ok"
        assert files["audio"].exists()
        assert files["profile"].exists()
        assert report["summary"]["candidate_count"] == 2


def test_apply_requires_approval_note() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_root(root)
        seed_files(root)

        report = apply_script.build_report(target="audio_tools_cache", apply=True, approval_note=None)

        assert report["validation"]["status"] == "blocked"
        assert "explicit_owner_approval_note_required_for_apply" in report["validation"]["errors"]


def test_apply_moves_audio_and_profile_to_rollback() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_root(root)
        files = seed_files(root)

        report = apply_script.build_report(target="all", apply=True, approval_note="approved by owner")

        assert report["validation"]["status"] == "ok"
        assert report["summary"]["moved_count"] == 2
        assert not files["audio"].exists()
        assert not files["profile"].exists()
        moved = [
            record
            for target_report in report["target_reports"]
            for record in target_report["moved_records"]
        ]
        assert len(moved) == 2
        for record in moved:
            rollback = root / record["rollback_copy"]
            assert rollback.exists()
            assert apply_script.file_sha256(rollback) == record["sha256"]


def test_path_outside_workspace_blocks() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        configure_root(root)
        outside = root.parent / "outside.txt"
        outside.write_text("x", encoding="utf-8")
        try:
            try:
                apply_script.ensure_inside_workspace(outside)
            except ValueError as exc:
                assert "path_outside_workspace" in str(exc)
            else:
                raise AssertionError("outside path did not block")
        finally:
            outside.unlink(missing_ok=True)
