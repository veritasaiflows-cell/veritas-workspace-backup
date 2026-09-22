#!/usr/bin/env python3
"""Regressions for WF74 cron duplication owner-runner classification."""
from __future__ import annotations

from wf74_cron_duplication_audit import (
    OWNER_JOB,
    OWNER_RUNNER_TOKEN,
    actionable_hits,
    classify_enabled_jobs,
    job_hits,
)


def owner_command_job() -> dict[str, object]:
    return {
        "id": "b911d479-13aa-48fe-b662-937e08450363",
        "name": OWNER_JOB,
        "enabled": True,
        "schedule": {"kind": "cron", "expr": "40 21 * * *", "tz": "America/Phoenix"},
        "payload": {
            "kind": "command",
            "argv": [
                r"C:\Users\Veritas\AppData\Local\Programs\Python\Python313\python.exe",
                r"scripts\wf74_model_quality_collection_cron_runner.py",
                "--write",
                "--write-md",
                "--validate",
                "--cron-nonblocking-domain-exit",
            ],
        },
    }


def test_full_path_command_argv_is_owner_runner() -> None:
    hits = job_hits(owner_command_job())
    assert hits == [OWNER_RUNNER_TOKEN]
    classified = classify_enabled_jobs([owner_command_job()])
    assert classified["expected_owner_ok"] is True
    assert classified["owner_runner_jobs"][0]["name"] == OWNER_JOB


def test_name_only_owner_job_without_argv_is_not_ok() -> None:
    job = {
        "id": "name-only",
        "name": OWNER_JOB,
        "enabled": True,
        "payload": {"kind": "command", "argv": []},
        "schedule": {"kind": "cron"},
    }
    classified = classify_enabled_jobs([job])
    assert classified["expected_owner_ok"] is False
    assert classified["owner_job_matches"][0]["hits"] == []


def test_reminder_do_not_execute_is_not_a_collector() -> None:
    text = (
        "Do not execute python scripts/otel_ops_control.py from this reminder.\n"
        "Owner collector is Ops - OTEL Local Digest."
    )
    assert actionable_hits(text) == []


def test_duplicate_component_command_outside_owner_is_flagged() -> None:
    extra = {
        "id": "dup",
        "name": "Ops - Extra OTEL Control",
        "enabled": True,
        "schedule": {"kind": "cron", "expr": "0 0 * * *"},
        "payload": {
            "kind": "command",
            "argv": [
                r"C:\Python\python.exe",
                r"scripts\otel_ops_control.py",
                "--write",
                "--validate",
            ],
        },
    }
    classified = classify_enabled_jobs([owner_command_job(), extra])
    assert classified["expected_owner_ok"] is True
    assert len(classified["recurring_component_outside_owner"]) == 1


def main() -> int:
    test_full_path_command_argv_is_owner_runner()
    test_name_only_owner_job_without_argv_is_not_ok()
    test_reminder_do_not_execute_is_not_a_collector()
    test_duplicate_component_command_outside_owner_is_flagged()
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
