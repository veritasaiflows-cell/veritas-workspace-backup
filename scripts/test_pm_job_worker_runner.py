#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pm_job_worker_runner as worker


def test_implementation_plan_payload_never_authorizes_patch() -> None:
    payload = worker.implementation_plan_payload({
        "job_id": "pm-test",
        "title": "Test plan",
        "automation_class": "implementation_plan",
        "target_files": ["scripts/example.py"],
        "proof_commands": ["python scripts\\example.py --write --validate"],
    })
    assert payload["recommended_executor"] == "main_or_main_spawned_helper"
    assert "No unattended code patch." in payload["stop_lines"]
    assert "Cron does not patch code." in payload["next_action"]


def test_worker_authority_boundary_blocks_mutation() -> None:
    boundary = worker.AUTHORITY_BOUNDARY
    assert boundary["patches_code"] is False
    assert boundary["spawns_helpers"] is False
    assert boundary["cron_schedule_mutation_allowed"] is False
    assert boundary["canon_or_portfolio_mutation_allowed"] is False
    assert boundary["paper_or_live_execution_allowed"] is False


def test_worker_state_distinguishes_plan_from_execution() -> None:
    original_tmp = worker.TMP
    with tempfile.TemporaryDirectory() as tmp:
        try:
            worker.TMP = Path(tmp)
            state = worker.worker_state(
                selected_job_id="pm-test",
                action_type="prepare_implementation_plan",
                executed=False,
                implementation_plan={"job_id": "pm-test"},
                execution_results=[],
            )
        finally:
            worker.TMP = original_tmp
    assert state["candidate_selected"] is True
    assert state["lane_prepared"] is True
    assert state["proof_executed"] is False
    assert state["terminal_state"] == "plan_prepared_for_main"


def test_prefilter_reuses_only_fresh_quiet_no_action_packet() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    signature = {"hash": "abc123", "source_count": 1, "sources": []}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "pm-worker.json"
        out.write_text(
            json.dumps(
                {
                    "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
                    "status": "quiet_success",
                    "summary": {"action_type": "no_action"},
                    "validation": {"status": "ok"},
                    "input_signature": signature,
                }
            ),
            encoding="utf-8",
        )

        decision = worker.prefilter_decision(out, signature, now=now)

    assert decision["can_reuse_existing_packet"] is True
    assert decision["reason"] == "unchanged_inputs_and_fresh_no_action"


def test_input_signature_includes_execution_context() -> None:
    cron = worker.build_input_signature("cron")
    main = worker.build_input_signature("main")

    assert cron["hash"] != main["hash"]
    assert cron["sources"][0]["label"] == "execution_context"
    assert cron["sources"][0]["context"] == "cron"
    assert main["sources"][0]["context"] == "main"


def test_lane_register_signature_tracks_only_active_collision_groups() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "lane-register.json"
        path.write_text(
            json.dumps(
                {
                    "lanes": [
                        {
                            "status": "running",
                            "workflow_id": "WF88",
                            "workstream_id": "token-prefilter",
                            "collision_group": "pm-worker",
                            "notes": ["first note"],
                        },
                        {
                            "status": "complete",
                            "workflow_id": "WF88",
                            "workstream_id": "old-work",
                            "collision_group": "completed-group",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        first = worker.lane_register_collision_state(path)

        path.write_text(
            json.dumps(
                {
                    "lanes": [
                        {
                            "status": "running",
                            "workflow_id": "WF88",
                            "workstream_id": "token-prefilter",
                            "collision_group": "pm-worker",
                            "notes": ["normal bookkeeping changed"],
                        },
                        {
                            "status": "complete",
                            "workflow_id": "WF88",
                            "workstream_id": "old-work",
                            "collision_group": "completed-group",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        unchanged = worker.lane_register_collision_state(path)

        path.write_text(
            json.dumps(
                {
                    "lanes": [
                        {
                            "status": "running",
                            "workflow_id": "WF88",
                            "workstream_id": "token-prefilter",
                            "collision_group": "pm-worker",
                        },
                        {
                            "status": "leased",
                            "workflow_id": "WF74",
                            "workstream_id": "new-work",
                            "collision_group": "new-active-group",
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        changed = worker.lane_register_collision_state(path)

    assert first["sha256"] == unchanged["sha256"]
    assert first["sha256"] != changed["sha256"]
    assert "completed-group" not in first["groups"]
    assert "new-active-group" in changed["groups"]


def test_prefilter_refreshes_when_prior_packet_selected_work_or_is_stale() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    signature = {"hash": "abc123", "source_count": 1, "sources": []}
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "pm-worker.json"
        out.write_text(
            json.dumps(
                {
                    "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
                    "status": "ok",
                    "summary": {"action_type": "run_proof_refresh"},
                    "validation": {"status": "ok"},
                    "input_signature": signature,
                }
            ),
            encoding="utf-8",
        )
        selected_work = worker.prefilter_decision(out, signature, now=now)

        out.write_text(
            json.dumps(
                {
                    "generated_at_utc": (now - timedelta(hours=worker.PREFILTER_MAX_AGE_HOURS + 1)).isoformat().replace("+00:00", "Z"),
                    "status": "quiet_success",
                    "summary": {"action_type": "no_action"},
                    "validation": {"status": "ok"},
                    "input_signature": signature,
                }
            ),
            encoding="utf-8",
        )
        stale = worker.prefilter_decision(out, signature, now=now)

    assert selected_work["can_reuse_existing_packet"] is False
    assert selected_work["reason"] == "previous_packet_not_quiet_no_action"
    assert stale["can_reuse_existing_packet"] is False
    assert stale["reason"] == "previous_packet_not_fresh"


def test_main_writes_post_refresh_input_signature() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "pm-worker.json"
        signatures = [
            {"hash": "pre-refresh", "source_count": 1, "sources": []},
            {"hash": "post-refresh", "source_count": 1, "sources": []},
        ]
        original_argv = sys.argv
        original_build_input_signature = worker.build_input_signature
        original_prefilter_decision = worker.prefilter_decision
        original_build_report = worker.build_report
        try:
            sys.argv = [
                "pm_job_worker_runner.py",
                "--write",
                "--validate",
                "--out",
                str(out),
            ]
            worker.build_input_signature = lambda execution_context="cron": signatures.pop(0)  # type: ignore[assignment]
            worker.prefilter_decision = lambda out_path, current_signature: {  # type: ignore[assignment]
                "status": "refresh_required",
                "can_reuse_existing_packet": False,
                "reason": "source_signature_changed",
            }
            worker.build_report = lambda args: {  # type: ignore[assignment]
                "schema": worker.SCHEMA,
                "generated_at_utc": worker.utc_now(),
                "status": "quiet_success",
                "mode": "dry_run",
                "summary": {"action_type": "no_action", "selected_job_id": None},
                "validation": {"status": "ok", "errors": [], "warnings": []},
            }

            assert worker.main() == 0

            payload = json.loads(out.read_text(encoding="utf-8"))
        finally:
            sys.argv = original_argv
            worker.build_input_signature = original_build_input_signature  # type: ignore[assignment]
            worker.prefilter_decision = original_prefilter_decision  # type: ignore[assignment]
            worker.build_report = original_build_report  # type: ignore[assignment]

    assert payload["input_signature"]["hash"] == "post-refresh"


def main() -> int:
    test_implementation_plan_payload_never_authorizes_patch()
    test_worker_authority_boundary_blocks_mutation()
    test_worker_state_distinguishes_plan_from_execution()
    test_prefilter_reuses_only_fresh_quiet_no_action_packet()
    test_input_signature_includes_execution_context()
    test_lane_register_signature_tracks_only_active_collision_groups()
    test_prefilter_refreshes_when_prior_packet_selected_work_or_is_stale()
    test_main_writes_post_refresh_input_signature()
    print("pm_job_worker_runner_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
