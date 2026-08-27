#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pm_autonomous_worker_predispatch_prefilter as prefilter


def write_live_job(path: Path, message: str) -> None:
    path.write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "name": prefilter.JOB_NAME,
                        "id": "job-123",
                        "payload": {
                            "kind": "agentTurn",
                            "model": "openai/gpt-5.5",
                            "thinking": "medium",
                            "timeoutSeconds": 1800,
                            "message": message,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_proposal_builds_single_line_wrapper_payload() -> None:
    message = (
        "Execute exactly this single command:\n"
        "python scripts\\pm_job_worker_runner.py --refresh-frontdoors --execute --verify --write --validate\n"
        "Do not run any other commands."
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        live_path = Path(temp_dir) / "cron-list.json"
        write_live_job(live_path, message)
        proposal = prefilter.build_promotion_proposal(live_cron_path=live_path)

    assert proposal["apply_status"] == "not_applied"
    assert proposal["status"] == "proposal_ready"
    assert proposal["authority_boundary"]["cron_payload_mutation_allowed"] is False
    assert proposal["promotion_effect"]["eliminates_scheduled_agent_turn"] is False
    assert proposal["promotion_effect"]["agent_turn_to_command_migration_required_for_full_api_savings"] is True
    proposed_message = proposal["proposed_payload"]["message"]
    assert "\n" not in proposed_message
    assert "\r" not in proposed_message
    assert prefilter.PROPOSED_COMMAND in proposed_message
    assert prefilter.EXISTING_WORKER_COMMAND not in proposed_message
    assert proposal["proposal_shape"]["single_line_payload"] is True


def test_proposal_recognizes_already_promoted_payload() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        live_path = Path(temp_dir) / "cron-list.json"
        write_live_job(live_path, prefilter.proposed_single_line_message())
        proposal = prefilter.build_promotion_proposal(live_cron_path=live_path)

    assert proposal["status"] == "already_promoted"
    assert proposal["proposed_command_found"] is True
    assert proposal["proposal_shape"]["single_line_payload"] is True


def test_find_live_cron_job_handles_nested_inventory() -> None:
    payload = {
        "jobs": [
            {"name": "Other"},
            {
                "name": prefilter.JOB_NAME,
                "id": "job-123",
                "payload": {"kind": "agentTurn", "message": prefilter.EXISTING_WORKER_COMMAND},
            },
        ]
    }
    found = prefilter.find_live_cron_job(payload)
    assert found["id"] == "job-123"


def test_report_skips_when_worker_prefilter_reuses_packet(monkeypatch) -> None:
    signature = {"hash": "abc123", "source_count": 1, "sources": []}
    decision = {
        "status": "reuse_existing_packet",
        "can_reuse_existing_packet": True,
        "reason": "unchanged_inputs_and_fresh_no_action",
        "current_input_hash": "abc123",
    }

    monkeypatch.setattr(prefilter.worker, "build_input_signature", lambda execution_context: signature)
    monkeypatch.setattr(prefilter.worker, "prefilter_decision", lambda out, current_signature: decision)
    monkeypatch.setattr(
        prefilter,
        "build_promotion_proposal",
        lambda: {"status": "proposal_ready", "apply_status": "not_applied"},
    )

    args = type("Args", (), {"prefilter_only": True, "execute": False, "timeout_seconds": 1})()
    report = prefilter.build_report(args)

    assert report["status"] == "skipped_unchanged"
    assert report["would_spawn_model_or_agent_turn"] is False
    assert report["would_run_existing_worker"] is False
    assert report["validation"]["status"] == "ok"


def test_report_accepts_already_promoted_proposal(monkeypatch) -> None:
    signature = {"hash": "abc123", "source_count": 1, "sources": []}
    decision = {
        "status": "reuse_existing_packet",
        "can_reuse_existing_packet": True,
        "reason": "unchanged_inputs_and_fresh_no_action",
        "current_input_hash": "abc123",
    }

    monkeypatch.setattr(prefilter.worker, "build_input_signature", lambda execution_context: signature)
    monkeypatch.setattr(prefilter.worker, "prefilter_decision", lambda out, current_signature: decision)
    monkeypatch.setattr(
        prefilter,
        "build_promotion_proposal",
        lambda: {"status": "already_promoted", "apply_status": "not_applied"},
    )

    args = type("Args", (), {"prefilter_only": True, "execute": False, "timeout_seconds": 1})()
    report = prefilter.build_report(args)

    assert report["status"] == "skipped_unchanged"
    assert report["validation"]["status"] == "ok"
    assert "promotion_proposal_already_live" in report["validation"]["info"]


def test_report_blocks_failed_worker_execution(monkeypatch) -> None:
    signature = {"hash": "changed", "source_count": 1, "sources": []}
    decision = {
        "status": "refresh_required",
        "can_reuse_existing_packet": False,
        "reason": "source_signature_changed",
        "current_input_hash": "changed",
    }

    monkeypatch.setattr(prefilter.worker, "build_input_signature", lambda execution_context: signature)
    monkeypatch.setattr(prefilter.worker, "prefilter_decision", lambda out, current_signature: decision)
    monkeypatch.setattr(
        prefilter,
        "build_promotion_proposal",
        lambda: {"status": "proposal_ready", "apply_status": "not_applied"},
    )
    monkeypatch.setattr(
        prefilter,
        "execute_worker",
        lambda timeout_seconds: {
            "name": "pm_job_worker_runner",
            "returncode": 1,
            "ok": False,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )

    args = type("Args", (), {"prefilter_only": False, "execute": True, "timeout_seconds": 1})()
    report = prefilter.build_report(args)

    assert report["status"] == "blocked"
    assert report["validation"]["status"] == "blocked"
    assert "pm_job_worker_runner_failed" in report["validation"]["errors"]


def main() -> int:
    test_proposal_builds_single_line_wrapper_payload()
    test_proposal_recognizes_already_promoted_payload()
    test_find_live_cron_job_handles_nested_inventory()

    class MonkeyPatch:
        def __init__(self) -> None:
            self._changes = []

        def setattr(self, obj, name, value) -> None:
            self._changes.append((obj, name, getattr(obj, name)))
            setattr(obj, name, value)

        def undo(self) -> None:
            for obj, name, value in reversed(self._changes):
                setattr(obj, name, value)
            self._changes.clear()

    mp = MonkeyPatch()
    try:
        test_report_skips_when_worker_prefilter_reuses_packet(mp)
    finally:
        mp.undo()

    mp = MonkeyPatch()
    try:
        test_report_accepts_already_promoted_proposal(mp)
    finally:
        mp.undo()

    mp = MonkeyPatch()
    try:
        test_report_blocks_failed_worker_execution(mp)
    finally:
        mp.undo()

    print("pm_autonomous_worker_predispatch_prefilter_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
