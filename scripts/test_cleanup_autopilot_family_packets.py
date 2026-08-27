from __future__ import annotations

import json
import tempfile
from pathlib import Path

import cleanup_autopilot_family_packets as family_packets


def seed_workspace(root: Path) -> None:
    family_packets.ROOT = root
    family_packets.TMP = root / "tmp"
    family_packets.OUT_JSON = family_packets.TMP / "cleanup-autopilot-family-packets.json"
    family_packets.OUT_MD = family_packets.TMP / "cleanup-autopilot-family-packets.md"
    family_packets.FULL_READINESS = family_packets.TMP / "cleanup-autopilot-full-delete-readiness.json"
    family_packets.STALE_TEXT_APPLY = root / "scripts" / "cleanup_autopilot_stale_text_apply.py"
    family_packets.FAMILY_APPLY = root / "scripts" / "cleanup_autopilot_family_apply.py"

    tmp = family_packets.TMP
    tmp.mkdir(parents=True)
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    family_packets.STALE_TEXT_APPLY.write_text("# wrapper\n", encoding="utf-8")
    family_packets.FAMILY_APPLY.write_text("# wrapper\n", encoding="utf-8")

    db = tmp / "cache.sqlite"
    db.write_text("db", encoding="utf-8")
    otel = tmp / "otel-collector" / "archive" / "collector.err.old.log"
    otel.parent.mkdir(parents=True)
    otel.write_text("otel", encoding="utf-8")
    active_otel = tmp / "otel-collector" / "metrics.jsonl"
    active_otel.write_text("active", encoding="utf-8")
    empty_pb = tmp / "otel-collector" / "20260101T000000Z-metrics-empty.pb"
    empty_pb.write_bytes(b"")
    audio = tmp / "audio-tools" / ".cache" / "model.bin"
    audio.parent.mkdir(parents=True)
    audio.write_text("audio", encoding="utf-8")
    scratch_voice = tmp / "audio-tools" / "voice-123.wav"
    scratch_voice.write_bytes(b"voice")
    go_bin = tmp / "go-bin-backup-20260607" / "validator.exe"
    go_bin.parent.mkdir(parents=True)
    go_bin.write_text("go", encoding="utf-8")
    stale = tmp / "old-proof.json"
    stale.write_text('{"old": true}', encoding="utf-8")
    current = tmp / "current-proof.json"
    current.write_text("{}", encoding="utf-8")

    (root / "memory").mkdir()
    (root / "memory" / "2026-01-01.md").write_text(
        "Reference tmp/cache.sqlite and tmp/otel-collector for retention review.\n",
        encoding="utf-8",
    )

    stale_row = {
        "path": "tmp/old-proof.json",
        "bytes": stale.stat().st_size,
        "last_write_utc": "2026-01-01T00:00:00Z",
        "sha256": family_packets.file_sha256(stale),
        "reference_check": {
            "status": "ok",
            "exact_reference_count": 0,
            "basename_reference_count": 0,
        },
    }
    digest = family_packets.inventory_digest([stale_row])
    family_packets.FULL_READINESS.write_text(
        json.dumps(
            {
                "summary": {
                    "tmp_total_mb": 1.0,
                    "next_owner_ready_text_microbatch_digest": digest,
                },
                "next_owner_ready_text_microbatch": [stale_row],
                "protected_or_family_packet_required_sample": [
                    {
                        "path": "tmp/current-proof.json",
                        "bytes": current.stat().st_size,
                        "last_write_utc": "2026-01-01T00:00:00Z",
                        "protected_reasons": ["referenced_by_cron_or_control"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_family_packets_are_review_only_and_split_readiness() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root)

        packet = family_packets.build_packet(sample_limit=20)

        assert packet["schema"] == "veritas.cleanup_autopilot_family_packets.v1"
        assert packet["status"] == "cleanup_family_packets_ready_no_apply"
        assert packet["validation"]["status"] == "ok"
        assert packet["summary"]["full_3gb_one_shot_delete_ready"] is False
        assert packet["authority_boundary"]["delete_allowed_now"] is False

        families = {family["family_id"]: family for family in packet["families"]}
        assert families["sqlite_db_lifecycle"]["readiness_state"] == "blocked_requires_db_lifecycle_packet"
        assert families["otel_collector_runtime_cache"]["readiness_state"].startswith("blocked_runtime")
        assert families["otel_collector_runtime_cache"]["file_count"] == 1
        assert families["otel_collector_archived_logs"]["approval_ready_after_owner_phrase"] is True
        assert families["otel_collector_empty_pb_files"]["approval_ready_after_owner_phrase"] is True
        assert families["audio_tools_cache"]["readiness_state"] == "blocked_cache_rebuild_acceptance_required"
        assert families["audio_tools_scratch_voice_files"]["approval_ready_after_owner_phrase"] is True
        assert families["go_binary_current_cache"]["readiness_state"] == "blocked_current_validator_dependency"
        assert families["go_binary_backup_cache"]["readiness_state"] == "owner_ready_backup_only_after_exact_phrase"
        assert families["go_profile_binary_cache"]["readiness_state"] == "blocked_profile_route_review_required"
        assert families["go_binary_backup_cache"]["approval_ready_after_owner_phrase"] is True

        stale_family = families["stale_generated_text_proof_outputs"]
        assert stale_family["approval_ready_after_owner_phrase"] is True
        assert "Approve Cleanup Autopilot stale generated text microbatch" in stale_family["approval_surface"]["approval_phrase"]
        assert stale_family["delete_allowed_now"] is False

        current_proof = families["current_referenced_proof_outputs"]
        assert current_proof["readiness_state"] == "blocked_current_or_referenced_proof"
        assert current_proof["approval_ready_after_owner_phrase"] is False


def test_build_family_skips_files_that_vanish_during_inventory(monkeypatch) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_workspace(root)
        now = family_packets.datetime.now(family_packets.timezone.utc)
        stable = family_packets.TMP / "stable-proof.json"
        stable.write_text("stable", encoding="utf-8")
        vanishing = family_packets.TMP / "vanishing.sqlite-shm"
        vanishing.write_text("volatile", encoding="utf-8")
        original_file_record = family_packets.file_record

        def file_record_with_vanish(path, now_arg, *, include_sha=False):
            if path == vanishing:
                vanishing.unlink()
            return original_file_record(path, now_arg, include_sha=include_sha)

        monkeypatch.setattr(family_packets, "file_record", file_record_with_vanish)

        family = family_packets.build_family(
            family_id="volatile_test",
            title="Volatile Test",
            description="Test vanished files are skipped.",
            files=[stable, vanishing],
            now=now,
            reference_terms=[],
            reference_corpus=[],
            reference_truncated=False,
            readiness_state="test",
            deletion_boundary="test",
            next_action="test",
            sample_limit=20,
        )

        assert family["file_count"] == 1
        assert family["records"][0]["path"] == "tmp/stable-proof.json"
