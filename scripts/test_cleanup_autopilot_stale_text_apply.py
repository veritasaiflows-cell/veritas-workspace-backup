from __future__ import annotations

import json
import tempfile
from pathlib import Path

import cleanup_autopilot_stale_text_apply as apply_script


def seed_workspace(root: Path) -> tuple[Path, str]:
    apply_script.ROOT = root
    apply_script.TMP = root / "tmp"
    apply_script.STATE = root / "state"
    apply_script.PACKET = apply_script.TMP / "cleanup-autopilot-full-delete-readiness.json"
    apply_script.APPLY_REPORT = apply_script.TMP / "cleanup-autopilot-stale-text-apply-report.json"
    apply_script.ROLLBACK_ROOT = root / "state" / "tmp-lifecycle-rollback" / "cleanup-autopilot-stale-text"
    target = apply_script.TMP / "old-debug.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"debug": true}', encoding="utf-8")
    row = {
        "path": "tmp/old-debug.json",
        "bytes": target.stat().st_size,
        "sha256": apply_script.file_sha256(target),
        "last_write_utc": "2026-01-01T00:00:00Z",
        "reference_check": {
            "status": "ok",
            "exact_reference_count": 0,
            "basename_reference_count": 0,
        },
    }
    digest = apply_script.microbatch_digest([row])
    phrase = (
        "Approve Cleanup Autopilot stale generated text microbatch "
        f"{digest} exactly as listed in tmp/cleanup-autopilot-full-delete-readiness.json."
    )
    apply_script.PACKET.write_text(
        json.dumps(
            {
                "summary": {
                    "next_owner_ready_text_microbatch_digest": digest,
                    "next_owner_ready_text_microbatch_count": 1,
                },
                "approval_surface": {
                    "approval_phrase_for_future_stale_text_apply": phrase,
                    "delete_allowed_now": False,
                },
                "next_owner_ready_text_microbatch": [row],
            }
        ),
        encoding="utf-8",
    )
    return target, phrase


def test_dry_run_does_not_delete() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        target, phrase = seed_workspace(Path(tmpdir))
        report = apply_script.build_report(apply=False, approval_phrase=phrase)
        assert report["validation"]["status"] == "ok"
        assert report["status"] == "dry_run_ok"
        assert target.exists()


def test_apply_requires_exact_phrase() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        target, _phrase = seed_workspace(Path(tmpdir))
        report = apply_script.build_report(apply=True, approval_phrase="wrong")
        assert report["validation"]["status"] == "blocked"
        assert "approval_phrase_mismatch" in report["validation"]["errors"]
        assert target.exists()


def test_apply_deletes_after_rollback_copy() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        target, phrase = seed_workspace(root)
        report = apply_script.build_report(apply=True, approval_phrase=phrase)
        assert report["validation"]["status"] == "ok"
        assert report["summary"]["deleted_count"] == 1
        assert not target.exists()
        rollback = root / report["deleted_records"][0]["rollback_copy"]
        assert rollback.exists()


def test_reference_hit_blocks_apply() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        target, phrase = seed_workspace(Path(tmpdir))
        payload = json.loads(apply_script.PACKET.read_text(encoding="utf-8"))
        payload["next_owner_ready_text_microbatch"][0]["reference_check"]["basename_reference_count"] = 1
        apply_script.PACKET.write_text(json.dumps(payload), encoding="utf-8")
        report = apply_script.build_report(apply=True, approval_phrase=phrase)
        assert report["validation"]["status"] == "blocked"
        assert any(error.startswith("basename_references_not_zero:") for error in report["validation"]["errors"])
        assert target.exists()
