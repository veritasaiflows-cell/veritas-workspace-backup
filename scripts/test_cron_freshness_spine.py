#!/usr/bin/env python3
"""Focused regressions for cron freshness spine warning classification."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from cron_freshness_spine import JOB_CONTRACTS, artifact_record, attention_bucket, attention_class, build_payload, expected_warning_quiet


def test_quote_first_warning_is_quiet_with_nonfresh_backlog() -> None:
    payload = {
        "status": "warning",
        "validation": {
            "status": "ok",
            "warnings": ["wf78_event_queue_keeps_fresh_quote_first"],
        },
        "summary": {
            "critical_count": 0,
            "missing_required_symbols": [],
            "nonfresh_snapshot_count": 21,
            "stale_or_missing_snapshot_count": 0,
        },
    }

    assert expected_warning_quiet(payload) is True


def test_quote_first_warning_does_not_quiet_stale_or_critical() -> None:
    critical_payload = {
        "status": "warning",
        "validation": {
            "status": "ok",
            "warnings": ["wf78_event_queue_keeps_fresh_quote_first"],
        },
        "summary": {
            "critical_count": 1,
            "missing_required_symbols": [],
            "nonfresh_snapshot_count": 0,
            "stale_or_missing_snapshot_count": 0,
        },
    }
    stale_payload = {
        "status": "warning",
        "validation": {
            "status": "ok",
            "warnings": ["wf78_event_queue_keeps_fresh_quote_first"],
        },
        "summary": {
            "critical_count": 0,
            "missing_required_symbols": [],
            "nonfresh_snapshot_count": 0,
            "stale_or_missing_snapshot_count": 1,
        },
    }

    assert expected_warning_quiet(critical_payload) is False
    assert expected_warning_quiet(stale_payload) is False


def test_no_reply_operator_action_is_not_handoff() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "trade-grade-os-freshness-cron-runner.json"
        path.write_text(
            json.dumps(
                {
                    "status": "ok",
                    "operator_action": "NO_REPLY",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {"status": "ok"},
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "trade_grade_os_freshness_cron_runner",
                "path": str(path),
                "required": True,
            },
            default_freshness_hours=36,
        )

    assert record["operator_action"] == "NO_REPLY"
    assert record["main_handoff_semantic"] is False
    assert record["owner_decision_semantic"] is False


def test_cron_operator_ledger_warning_rollup_quiet_only_when_clean() -> None:
    payload = {
        "schema_version": 1,
        "status": "warning",
        "operator_attention": {
            "stop_line_windows": [],
            "blocked_windows": [],
            "warning_windows": ["morning", "post-close"],
        },
        "artifact_inventory": {
            "missing_required_roles": [],
            "critical_or_unreadable_roles": [],
        },
    }
    blocked_payload = {
        **payload,
        "operator_attention": {
            "stop_line_windows": [],
            "blocked_windows": ["post-close"],
            "warning_windows": ["morning"],
        },
    }

    assert expected_warning_quiet(payload) is True
    assert expected_warning_quiet(blocked_payload) is False


def test_attention_class_separates_known_review_from_new_review() -> None:
    job = {
        "name": "Finance - Ticker Card Freshness Owner Runner",
        "signal_class": "MAIN_SESSION_REQUIRED",
        "status": "needs_review",
        "reason": "artifact_requests_or_warns_for_review",
    }
    previous_jobs = {
        job["name"]: {
            "signal_class": "MAIN_SESSION_REQUIRED",
            "status": "needs_review",
            "reason": "artifact_requests_or_warns_for_review",
        }
    }
    changed_previous = {
        job["name"]: {
            "signal_class": "NO_REPLY",
            "status": "fresh",
            "reason": "required_artifacts_fresh",
        }
    }

    assert attention_class(job, previous_jobs) == "known_monitor_only"
    assert attention_class(job, changed_previous) == "new_or_changed"


def test_known_review_uses_underlying_signal_when_prior_run_was_quieted() -> None:
    job = {
        "name": "Finance - Ticker Card Freshness Owner Runner",
        "signal_class": "MAIN_SESSION_REQUIRED",
        "status": "needs_review",
        "reason": "artifact_requests_or_warns_for_review",
        "underlying_signal_class": "MAIN_SESSION_REQUIRED",
        "underlying_status": "needs_review",
        "underlying_reason": "artifact_requests_or_warns_for_review",
    }
    previous_jobs = {
        job["name"]: {
            "signal_class": "NO_REPLY",
            "status": "standing_review_quiet",
            "reason": "standing_review_quiet",
            "underlying_signal_class": "MAIN_SESSION_REQUIRED",
            "underlying_status": "needs_review",
            "underlying_reason": "artifact_requests_or_warns_for_review",
        }
    }

    assert attention_class(job, previous_jobs) == "known_monitor_only"


def test_known_monitor_only_bucket_is_quiet_success() -> None:
    job = {
        "signal_class": "NO_REPLY",
        "standing_review_quiet": True,
    }

    assert attention_bucket(job) == "quiet_success"


def test_standing_review_quiet_removes_stable_review_from_attention_queue() -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        proof = tmp_path / "review-proof.json"
        ledger = tmp_path / "cron-ledger.json"
        operating = tmp_path / "operating-spine.json"
        out = tmp_path / "cron-freshness-spine.json"
        proof.write_text(
            json.dumps({"status": "warning", "generated_at_utc": now, "validation": {"status": "ok", "warnings": ["review"]}}),
            encoding="utf-8",
        )
        ledger.write_text(
            json.dumps(
                {
                    "jobs": [
                        {
                            "id": "test-job",
                            "name": "Finance - Morning Control Digest Proof Refresh",
                            "enabled": True,
                            "schedule": {"expr": "12 7 * * 1-5", "kind": "cron", "tz": "America/Phoenix"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        operating.write_text(json.dumps({"implemented_phases": []}), encoding="utf-8")
        out.write_text(
            json.dumps(
                {
                    "jobs": [
                        {
                            "name": "Finance - Morning Control Digest Proof Refresh",
                            "signal_class": "MAIN_SESSION_REQUIRED",
                            "status": "needs_review",
                            "reason": "artifact_requests_or_warns_for_review",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        payload = build_payload(ledger, operating, out_path=out, job_contracts={
            "Finance - Morning Control Digest Proof Refresh": {
                "owner_workflow": "test",
                "freshness_hours": 36,
                "expected_artifacts": [{"path": str(proof), "role": "proof", "required": True, "blocking": True}],
            }
        })

    summary = payload["summary"]
    assert payload["status"] == "ok"
    assert summary["requires_attention_count"] == 0
    assert summary["review_queue_count"] == 0
    assert summary["standing_review_quiet_count"] == 1
    assert payload["jobs"][0]["standing_review_quiet"] is True


def test_paper_positions_blocked_packet_is_review_only_handoff_not_urgent_blocker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "paper-positions.json"
        path.write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {"status": "ok"},
                    "authority_boundary": {
                        "trade_or_account_action_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "paper_positions_state",
                "path": str(path),
                "required": True,
                "blocking": True,
            },
            default_freshness_hours=36,
        )

    assert record["blocked_semantic"] is False
    assert record["review_only_blocked_semantic"] is True
    assert record["main_handoff_semantic"] is True
    assert record["authority_widened"] is False


def test_wf87_runtime_blocked_packet_is_review_only_handoff_not_urgent_blocker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "wf87-position-sizing-runtime-check.json"
        path.write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {"status": "ok"},
                    "authority_boundary": {
                        "paper_or_live_execution_allowed": False,
                        "brokerage_or_account_action_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "wf87_position_sizing_runtime_check",
                "path": str(path),
                "required": True,
                "blocking": True,
            },
            default_freshness_hours=12,
        )

    assert record["blocked_semantic"] is False
    assert record["review_only_blocked_semantic"] is True
    assert record["main_handoff_semantic"] is True
    assert record["authority_widened"] is False


def test_wf85_delivered_blocker_is_review_only_handoff_not_urgent_blocker() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "wf85-paper-deployment-telegram-cron-runner.json"
        path.write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "operator_action": "TELEGRAM_BLOCKER_SENT",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {"status": "ok"},
                    "authority_boundary": {
                        "paper_or_live_execution_allowed": False,
                        "brokerage_or_account_action_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "wf85_paper_deployment_telegram_cron_runner",
                "path": str(path),
                "required": True,
                "blocking": True,
            },
            default_freshness_hours=18,
        )

    assert record["blocked_semantic"] is False
    assert record["review_only_blocked_semantic"] is True
    assert record["main_handoff_semantic"] is True
    assert record["authority_widened"] is False


def test_wf85_undelivered_blocker_stays_urgent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "wf85-paper-deployment-telegram-cron-runner.json"
        path.write_text(
            json.dumps(
                {
                    "status": "blocked",
                    "operator_action": "BLOCKED",
                    "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                    "validation": {"status": "blocked", "errors": ["blocked_digest_not_delivered"]},
                    "authority_boundary": {
                        "paper_or_live_execution_allowed": False,
                        "brokerage_or_account_action_allowed": False,
                        "owner_approval_inferred": False,
                    },
                }
            ),
            encoding="utf-8",
        )

        record = artifact_record(
            {
                "role": "wf85_paper_deployment_telegram_cron_runner",
                "path": str(path),
                "required": True,
                "blocking": True,
            },
            default_freshness_hours=18,
        )

    assert record["blocked_semantic"] is True
    assert record["review_only_blocked_semantic"] is False
    assert record["main_handoff_semantic"] is False
    assert record["operator_action"] == "BLOCKED"


def test_wf85_radar_treats_wf85_runner_as_nonblocking_source_context() -> None:
    for job_name in (
        "Finance - WF85 Paper Deployment Telegram Radar",
        "Finance - WF85 Open-Ready Telegram Radar",
        "Finance - WF85 Post-Refresh Paper Deployment Telegram Radar",
    ):
        specs = JOB_CONTRACTS[job_name]["expected_artifacts"]
        runner_specs = [item for item in specs if item["role"] == "trade_grade_os_freshness_cron_runner"]
        assert runner_specs, job_name
        assert runner_specs[0]["blocking"] is False


if __name__ == "__main__":
    test_quote_first_warning_is_quiet_with_nonfresh_backlog()
    test_quote_first_warning_does_not_quiet_stale_or_critical()
    test_no_reply_operator_action_is_not_handoff()
    test_cron_operator_ledger_warning_rollup_quiet_only_when_clean()
    test_attention_class_separates_known_review_from_new_review()
    test_known_review_uses_underlying_signal_when_prior_run_was_quieted()
    test_known_monitor_only_bucket_is_quiet_success()
    test_standing_review_quiet_removes_stable_review_from_attention_queue()
    test_paper_positions_blocked_packet_is_review_only_handoff_not_urgent_blocker()
    test_wf87_runtime_blocked_packet_is_review_only_handoff_not_urgent_blocker()
    test_wf85_delivered_blocker_is_review_only_handoff_not_urgent_blocker()
    test_wf85_undelivered_blocker_stays_urgent()
    test_wf85_radar_treats_wf85_runner_as_nonblocking_source_context()
    print("cron_freshness_spine_tests_passed")
