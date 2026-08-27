from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import cleanup_autopilot_full_delete_readiness as readiness


def old(path: Path) -> None:
    old_time = time.time() - 40 * 24 * 60 * 60
    os.utime(path, (old_time, old_time))


def seed_workspace(root: Path) -> dict:
    readiness.ROOT = root
    readiness.TMP = root / "tmp"
    readiness.OUT_JSON = readiness.TMP / "cleanup-autopilot-full-delete-readiness.json"
    readiness.OUT_MD = readiness.TMP / "cleanup-autopilot-full-delete-readiness.md"
    tmp = readiness.TMP
    tmp.mkdir(parents=True)
    current = tmp / "current-proof.json"
    current.write_text("{}", encoding="utf-8")
    old_json = tmp / "old-generated.json"
    old_json.write_text('{"old": true}', encoding="utf-8")
    old_tmp = tmp / ".old-generated.json.abc.tmp"
    old_tmp.write_text("tmp", encoding="utf-8")
    db = tmp / "cache.sqlite"
    db.write_text("sqlite", encoding="utf-8")
    vendor = tmp / "audio-tools" / "node_modules" / "pkg" / "cache.bin"
    vendor.parent.mkdir(parents=True)
    vendor.write_text("vendor", encoding="utf-8")
    for path in (old_json, old_tmp, db, vendor):
        old(path)
    return {
        "cron_control": {
            "jobs": [
                {
                    "expected_artifacts": [
                        {"path": "tmp/current-proof.json"},
                    ]
                }
            ]
        },
        "cron_freshness": {},
        "tmp_lifecycle_guard": {},
        "tmp_cleanup_report": {},
        "phase1_packet": {},
        "phase1_apply_report": {"summary": {"deleted_count": 1, "deleted_bytes": 10}},
    }


def test_full_delete_readiness_is_review_only_and_classifies_families() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts = seed_workspace(Path(tmpdir))

        packet = readiness.build_packet(artifacts, sample_limit=10)

        assert packet["schema"] == "veritas.cleanup_autopilot_full_delete_readiness.v1"
        assert packet["validation"]["status"] == "ok"
        assert packet["summary"]["safe_atomic_candidate_count"] == 1
        assert packet["summary"]["stale_generated_text_review_count"] == 1
        assert packet["summary"]["next_owner_ready_text_microbatch_count"] == 1
        assert packet["summary"]["protected_or_family_packet_required_count"] == 3
        assert packet["full_3gb_readiness"]["one_shot_delete_ready"] is False
        assert packet["approval_surface"]["stale_text_microbatch_ready"] is True
        assert packet["next_owner_ready_text_microbatch"][0]["path"] == "tmp/old-generated.json"

        boundary = packet["authority_boundary"]
        for flag in (
            "delete_allowed",
            "archive_allowed",
            "move_allowed",
            "broad_tmp_cleanup_allowed",
            "cron_schedule_mutation_allowed",
            "config_auth_runtime_mutation_allowed",
            "finance_canon_or_portfolio_mutation_allowed",
            "paper_or_live_execution_allowed",
            "brokerage_or_account_action_allowed",
            "owner_approval_inferred",
        ):
            assert boundary[flag] is False, flag
