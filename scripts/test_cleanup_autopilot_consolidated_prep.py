from __future__ import annotations

import json
import tempfile
from pathlib import Path

import cleanup_autopilot_consolidated_prep as prep


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def seed_packets(root: Path) -> None:
    prep.ROOT = root
    prep.TMP = root / "tmp"
    prep.OUT_JSON = prep.TMP / "cleanup-autopilot-consolidated-prep.json"
    prep.OUT_MD = prep.TMP / "cleanup-autopilot-consolidated-prep.md"
    prep.FULL_READINESS = prep.TMP / "cleanup-autopilot-full-delete-readiness.json"
    prep.FAMILY_PACKETS = prep.TMP / "cleanup-autopilot-family-packets.json"
    prep.DB_MANIFEST = prep.TMP / "db-lifecycle-manifest.json"
    prep.DB_ARCHIVE_PACKET = prep.TMP / "db-lifecycle-archive-approval-packet.json"
    prep.OTEL_RETENTION = prep.TMP / "otel-log-retention.json"
    prep.OTEL_OPS = prep.TMP / "otel-ops-control.json"
    prep.GO_FRESHNESS = prep.TMP / "go-binary-freshness-guard.json"

    write_json(
        prep.FULL_READINESS,
        {
            "status": "ok",
            "summary": {"tmp_total_mb": 3000.0},
            "validation": {"status": "ok", "errors": [], "warnings": []},
        },
    )
    write_json(
        prep.FAMILY_PACKETS,
        {
            "status": "cleanup_family_packets_ready_no_apply",
            "summary": {"family_mb": 2500.0},
            "validation": {"status": "ok", "errors": [], "warnings": []},
            "families": [
                {
                    "family_id": "audio_tools_scratch_voice_files",
                    "readiness_state": "owner_ready_scratch_voice_after_exact_phrase",
                    "file_count": 2,
                    "bytes": 100,
                    "mb": 0.001,
                    "inventory_digest": "abc",
                    "approval_ready_after_owner_phrase": True,
                    "next_action": "approve exact phrase",
                    "deletion_boundary": "scratch only",
                    "approval_surface": {
                        "approval_phrase": "Approve Cleanup Autopilot audio_tools_scratch_voice_files microbatch abc exactly as listed in tmp/cleanup-autopilot-family-packets.json.",
                        "apply_wrapper": "scripts/cleanup_autopilot_family_apply.py",
                    },
                },
                {
                    "family_id": "sqlite_db_lifecycle",
                    "readiness_state": "blocked_requires_db_lifecycle_packet",
                    "file_count": 5,
                    "bytes": 200,
                    "mb": 0.002,
                    "inventory_digest": "def",
                    "approval_ready_after_owner_phrase": False,
                    "next_action": "run db lifecycle",
                    "deletion_boundary": "db blocked",
                    "approval_surface": {"approval_phrase": None},
                },
            ],
        },
    )
    write_json(
        prep.DB_MANIFEST,
        {
            "status": "ok",
            "summary": {
                "database_count": 5,
                "archive_candidate_count": 1,
                "archive_ready_count": 0,
                "delete_ready_count": 0,
            },
            "recommended_owner_decision": {"delete_now": []},
        },
    )
    write_json(prep.DB_ARCHIVE_PACKET, {"status": "owner_decision_required"})
    write_json(
        prep.OTEL_RETENTION,
        {
            "status": "ok",
            "action": "dry_run",
            "needs_rotation": True,
            "before": {"exists": True, "size_bytes": 999},
            "after": {"exists": True, "size_bytes": 999},
            "validation": {"status": "ok", "errors": [], "warnings": []},
        },
    )
    write_json(prep.OTEL_OPS, {"status": "ok", "summary": {"warning_count": 0}})
    write_json(
        prep.GO_FRESHNESS,
        {
            "status": "ok",
            "binary_count": 3,
            "stale_count": 0,
            "missing_count": 0,
            "operator_action": "NO_ESCALATION_NEEDED",
        },
    )


def test_consolidated_packet_bundles_ready_and_blocked_surfaces() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_packets(Path(tmpdir))

        packet = prep.build_packet(producer_results=[])

        assert packet["schema"] == "veritas.cleanup_autopilot_consolidated_prep.v1"
        assert packet["validation"]["status"] == "ok"
        assert packet["authority_boundary"]["delete_allowed_now"] is False
        assert packet["summary"]["owner_ready_delete_microbatch_count"] == 1
        assert packet["summary"]["blocked_or_requires_subpacket_family_count"] == 1
        assert packet["summary"]["full_cleanup_one_shot_ready"] is False
        assert packet["owner_ready_approval_phrases"][0].startswith("Approve Cleanup Autopilot")
        assert packet["blocked_full_cleanup_families"][0]["family_id"] == "sqlite_db_lifecycle"
        assert "Exact owner approval" in packet["skip_strategy"]["what_cannot_be_skipped"][0]


def test_validation_fails_when_source_packet_is_not_clean() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_packets(Path(tmpdir))
        data = json.loads(prep.FULL_READINESS.read_text(encoding="utf-8"))
        data["validation"]["status"] = "error"
        prep.FULL_READINESS.write_text(json.dumps(data), encoding="utf-8")

        packet = prep.build_packet(producer_results=[])

        assert packet["validation"]["status"] == "error"
        assert "full_delete_readiness_not_ok" in packet["validation"]["errors"]


def test_validation_allows_cached_optional_otel_ops_skip() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_packets(Path(tmpdir))

        packet = prep.build_packet(
            producer_results=[
                {
                    "id": "otel_ops_control",
                    "status": "skipped_cached_source",
                    "returncode": None,
                }
            ]
        )

        assert packet["validation"]["status"] == "ok"
        assert packet["producer_results"][0]["status"] == "skipped_cached_source"
