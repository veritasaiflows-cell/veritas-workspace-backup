from __future__ import annotations

import json
import tempfile
from pathlib import Path

import cleanup_autopilot_phase1_apply as apply_script


def write_packet(path: Path, row: dict, digest: str, approval_phrase: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema": "veritas.cleanup_autopilot_phase1.v1",
                "status": "owner_approval_ready_no_apply",
                "summary": {
                    "microbatch_digest": digest,
                    "microbatch_owner_approval_ready_count": 1,
                },
                "approval_surface": {
                    "approval_phrase_for_future_apply": approval_phrase,
                },
                "microbatch_candidates": [row],
            }
        ),
        encoding="utf-8",
    )


def seed_workspace(root: Path) -> tuple[Path, str]:
    apply_script.ROOT = root
    apply_script.TMP = root / "tmp"
    apply_script.STATE = root / "state"
    apply_script.PACKET = apply_script.TMP / "cleanup-autopilot-phase1.json"
    apply_script.APPLY_REPORT = apply_script.TMP / "cleanup-autopilot-phase1-apply-report.json"
    apply_script.ROLLBACK_ROOT = apply_script.STATE / "tmp-lifecycle-rollback" / "cleanup-autopilot-phase1"
    target = apply_script.TMP / ".old-proof.json.abc.tmp"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"old": true}', encoding="utf-8")
    row = {
        "path": "tmp/.old-proof.json.abc.tmp",
        "kind": "file",
        "bytes": target.stat().st_size,
        "sha256": apply_script.file_sha256(target),
        "newest_mtime_utc": "2026-01-01T00:00:00Z",
        "reference_check": {
            "status": "ok",
            "exact_reference_count": 0,
            "basename_reference_count": 0,
        },
    }
    digest = apply_script.packet_digest([row])
    phrase = f"Approve Cleanup Autopilot Phase 1 tmp microbatch {digest} exactly as listed."
    apply_script.APPROVAL_PHRASE = phrase
    write_packet(apply_script.PACKET, row, digest, phrase)
    return target, phrase


def test_dry_run_does_not_delete() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        target, phrase = seed_workspace(Path(tmpdir))

        report = apply_script.build_report(apply=False, approval_phrase=phrase)

        assert report["validation"]["status"] == "ok"
        assert report["status"] == "dry_run_ok"
        assert report["summary"]["deleted_count"] == 0
        assert target.exists()


def test_apply_requires_exact_phrase() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        target, _phrase = seed_workspace(Path(tmpdir))

        report = apply_script.build_report(apply=True, approval_phrase="wrong")

        assert report["validation"]["status"] == "blocked"
        assert "approval_phrase_mismatch" in report["validation"]["errors"]
        assert target.exists()


def test_apply_deletes_only_after_rollback_copy() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        target, phrase = seed_workspace(root)

        report = apply_script.build_report(apply=True, approval_phrase=phrase)

        assert report["validation"]["status"] == "ok"
        assert report["status"] == "applied_cleanup_autopilot_phase1_microbatch"
        assert report["summary"]["deleted_count"] == 1
        assert not target.exists()
        rollback = root / report["deleted_records"][0]["rollback_copy"]
        assert rollback.exists()
        assert apply_script.file_sha256(rollback) == report["deleted_records"][0]["sha256"]


def test_hash_mismatch_blocks_apply() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        target, phrase = seed_workspace(Path(tmpdir))
        payload = json.loads(apply_script.PACKET.read_text(encoding="utf-8"))
        payload["microbatch_candidates"][0]["sha256"] = "bad"
        apply_script.PACKET.write_text(json.dumps(payload), encoding="utf-8")

        report = apply_script.build_report(apply=True, approval_phrase=phrase)

        assert report["validation"]["status"] == "blocked"
        assert any(error.startswith("microbatch_digest_mismatch:") for error in report["validation"]["errors"])
        assert target.exists()

