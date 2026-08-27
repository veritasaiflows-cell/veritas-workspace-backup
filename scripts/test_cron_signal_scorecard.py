#!/usr/bin/env python3
from __future__ import annotations

import cron_signal_scorecard as scorecard


def test_quiets_replaced_morning_digest_signal() -> None:
    payload = {
        "jobs": [
            {
                "name": "Cron Reduction - Morning Control Digest",
                "enabled": True,
                "status": "standing_review_quiet",
                "attention_class": "known_monitor_only",
                "attention_bucket": "quiet_success",
            }
        ],
        "signals": [
            {
                "source": "operating_spine:morning_control_digest",
                "artifact": "tmp/morning-control-digest.json",
                "signal_class": "MAIN_SESSION_REQUIRED",
                "attention": "requires_main_attention",
                "status": "warning",
                "reason": "digest_requests_main_handoff",
            }
        ],
    }

    signals = scorecard.freshness_spine_signals(payload)

    assert signals[0]["signal_class"] == "NO_REPLY"
    assert signals[0]["attention"] == "quiet_success"
    assert signals[0]["reason"] == "paired_replacement_digest_standing_review_quiet"
    assert signals[0]["quieted_by_job"] == "Cron Reduction - Morning Control Digest"


def test_does_not_quiet_digest_signal_without_quiet_replacement() -> None:
    payload = {
        "jobs": [
            {
                "name": "Cron Reduction - Morning Control Digest",
                "enabled": True,
                "status": "blocked",
                "attention_class": "urgent",
                "attention_bucket": "urgent_blocked_or_owner_decision",
            }
        ],
        "signals": [
            {
                "source": "operating_spine:morning_control_digest",
                "artifact": "tmp/morning-control-digest.json",
                "signal_class": "MAIN_SESSION_REQUIRED",
                "attention": "requires_main_attention",
                "status": "warning",
                "reason": "digest_requests_main_handoff",
            }
        ],
    }

    signals = scorecard.freshness_spine_signals(payload)

    assert signals[0]["signal_class"] == "MAIN_SESSION_REQUIRED"
    assert signals[0]["attention"] == "requires_main_attention"
    assert "quieted_by_job" not in signals[0]


def test_quiets_replaced_post_close_digest_signal() -> None:
    payload = {
        "jobs": [
            {
                "name": "Cron Reduction - Post-Close Control Digest",
                "enabled": True,
                "standing_review_quiet": True,
            }
        ],
        "signals": [
            {
                "source": "operating_spine:post_close_control_digest",
                "artifact": "tmp/post-close-control-digest.json",
                "signal_class": "MAIN_SESSION_REQUIRED",
                "attention": "requires_main_attention",
                "status": "warning",
                "reason": "digest_requests_main_handoff",
            }
        ],
    }

    signals = scorecard.freshness_spine_signals(payload)

    assert signals[0]["signal_class"] == "NO_REPLY"
    assert signals[0]["attention"] == "quiet_success"
    assert signals[0]["quieted_by_job"] == "Cron Reduction - Post-Close Control Digest"


def test_blocked_signal_breakdown_separates_cron_jobs_from_operating_signals() -> None:
    signals = [
        {"source": "cron_job:Dynamic 300 Trade-Grade OS Freshness", "signal_class": "BLOCKED"},
        {"source": "operating_spine:morning_control_digest", "signal_class": "BLOCKED"},
        {"source": "sql_canon:finance_sql_canon_access", "signal_class": "BLOCKED"},
        {"source": "cron_job:Healthy Job", "signal_class": "NO_REPLY"},
    ]

    breakdown = scorecard.blocked_signal_breakdown(signals)

    assert len(breakdown["blocked"]) == 3
    assert len(breakdown["cron_job_blocked"]) == 1
    assert len(breakdown["operating_signal_blocked"]) == 1
    assert len(breakdown["non_cron_blocked"]) == 2


if __name__ == "__main__":
    test_quiets_replaced_morning_digest_signal()
    test_does_not_quiet_digest_signal_without_quiet_replacement()
    test_quiets_replaced_post_close_digest_signal()
    print("ok")
