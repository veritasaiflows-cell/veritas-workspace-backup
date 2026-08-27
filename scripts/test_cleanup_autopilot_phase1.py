from __future__ import annotations

import cleanup_autopilot_phase1 as autopilot


def test_cleanup_autopilot_phase1_stays_review_only() -> None:
    artifacts = {
        "tmp_cleanup_report": {
            "mode": "dry-run",
            "retention_days": 7,
            "summary": {
                "eligible_count": 2,
                "moved_count": 0,
                "candidate_digest": "a" * 64,
                "protected_violation_count": 0,
            },
            "candidates": [
                {
                    "path": "tmp/.old.json.abc.tmp",
                    "kind": "file",
                    "bytes": 10,
                    "newest_mtime_utc": "2026-01-01T00:00:00Z",
                    "sha256": "b" * 64,
                },
                {
                    "path": "tmp/dashboard-data.json",
                    "kind": "file",
                    "bytes": 10,
                    "newest_mtime_utc": "2026-01-01T00:00:00Z",
                    "sha256": "c" * 64,
                },
            ],
        },
        "tmp_lifecycle_guard": {},
        "wf88_cleanup_plan": {},
        "wf88_deletion_prep": {},
        "workspace_automation_approval": {},
    }

    packet = autopilot.build_packet(artifacts, microbatch_limit=5, reference_check=False)

    assert packet["schema"] == "veritas.cleanup_autopilot_phase1.v1"
    assert packet["validation"]["status"] == "ok"
    assert packet["summary"]["cleanup_candidate_count"] == 2
    assert packet["summary"]["safe_atomic_tmp_candidate_count"] == 1
    assert packet["summary"]["microbatch_review_count"] == 1
    assert packet["summary"]["microbatch_owner_approval_ready_count"] == 0

    boundary = packet["authority_boundary"]
    for flag in (
        "delete_archive_move_allowed",
        "cleanup_apply_allowed",
        "cron_schedule_mutation_allowed",
        "config_auth_runtime_mutation_allowed",
        "finance_canon_or_portfolio_mutation_allowed",
        "paper_or_live_execution_allowed",
        "owner_approval_inferred",
    ):
        assert boundary[flag] is False, flag

    assert packet["approval_surface"]["destructive_action_ready"] is False

