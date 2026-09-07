#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import deterministic_cron_sequence_runner as module


def spec(**overrides) -> module.JobSpec:
    base = {
        "key": "t",
        "job_id": "11111111-2222-3333-4444-555555555555",
        "title": "T",
        "out": module.TMP / "t.json",
        "history": module.STATE_HISTORY / "t.jsonl",
        "commands": [["scripts/tmp_cleanup.py", "--dry-run"]],
        "step_timeout": 60,
    }
    base.update(overrides)
    return module.JobSpec(**base)


def step(command="scripts/x.py", ok=True, error_code=None, **overrides) -> dict:
    base = {
        "command": [command],
        "ok": ok,
        "returncode": 0 if ok else 1,
        "error_code": error_code if not ok else None,
        "stderr_tail": "",
    }
    base.update(overrides)
    return base


def test_every_declared_command_exists_on_disk():
    # The whole point of the runner is that nothing is discovered at runtime, so
    # a typo in JOB_SPECS is a silent weekly no-op unless it is caught here.
    for key, job in module.JOB_SPECS.items():
        assert module.spec_errors(job) == [], (key, module.spec_errors(job))
        assert job.key == key
        assert job.commands


def test_job_ids_are_real_uuids_not_prefixes():
    for job in module.JOB_SPECS.values():
        parts = job.job_id.split("-")
        assert [len(p) for p in parts] == [8, 4, 4, 4, 12], job.job_id
        assert all(c in "0123456789abcdef-" for c in job.job_id), job.job_id


def test_spec_errors_reject_anything_outside_the_declared_script_surface():
    assert "spec_has_no_commands" in module.spec_errors(spec(commands=[]))
    assert "empty_command" in module.spec_errors(spec(commands=[[]]))
    problems = module.spec_errors(spec(commands=[["rm", "-rf", "/"]]))
    assert "command_not_a_workspace_script:rm" in problems
    problems = module.spec_errors(spec(commands=[["../outside.py"]]))
    assert "command_not_a_workspace_script:../outside.py" in problems
    problems = module.spec_errors(spec(commands=[["scripts/does_not_exist_xyz.py"]]))
    assert "command_script_missing:scripts/does_not_exist_xyz.py" in problems


def test_a_clean_run_is_ok_and_asks_for_no_reply():
    report = module.build_report(spec(), [step()], [], {"dispatched": False}, "2026-08-30T00:00:00Z")
    assert report["status"] == "ok"
    assert report["operator_action"] == "NO_REPLY"
    assert module.validate(report)["status"] == "ok"


def test_a_failed_step_blocks_and_names_the_command():
    steps = [step(), step("scripts/boom.py", ok=False, error_code="step_nonzero_exit")]
    report = module.build_report(spec(), steps, [], {"dispatched": True}, "2026-08-30T00:00:00Z")
    assert report["status"] == "blocked"
    assert report["operator_action"] == "MAIN_SESSION_REQUIRED"
    assert "step_failed:scripts/boom.py:step_nonzero_exit" in report["validation"]["errors"]
    assert report["summary"]["failed_commands"] == ["scripts/boom.py"]


def test_a_broken_spec_blocks_before_anything_runs():
    report = module.build_report(spec(), [], ["command_script_missing:scripts/x.py"], {"dispatched": False}, "2026-08-30T00:00:00Z")
    assert report["status"] == "blocked"
    assert "spec_invalid:command_script_missing:scripts/x.py" in report["validation"]["errors"]


def test_validate_rejects_a_widened_or_ungrounded_report():
    report = module.build_report(spec(), [step()], [], {"dispatched": False}, "2026-08-30T00:00:00Z")

    widened = dict(report, authority_boundary=dict(module.AUTHORITY_BOUNDARY, capital_deployment_allowed=True))
    assert "authority_boundary_mutated" in module.validate(widened)["errors"]

    assert "schema_mismatch" in module.validate(dict(report, schema="something.else"))["errors"]

    # A wake with no failure means the artifact does not justify the Main turn it caused.
    unjustified = dict(report, wake={"dispatched": True})
    assert "wake_dispatched_without_failure" in module.validate(unjustified)["errors"]

    miscounted = dict(report, summary=dict(report["summary"], executed_step_count=99))
    assert "step_count_mismatch" in module.validate(miscounted)["errors"]


def test_wake_message_reports_the_failure_without_granting_repair_authority():
    failed = [step("scripts/boom.py", ok=False, error_code="step_nonzero_exit", stderr_tail="ValidationError: drift")]
    message = module.build_wake_message(spec(), failed, module.TMP / "t.json")
    assert "scripts/boom.py" in message
    assert "ValidationError: drift" in message
    assert "Do not implement a repair" in message
    for boundary in ("cron", "config", "capital", "brokerage", "approval inference"):
        assert boundary in message


def test_dispatch_is_inert_in_dry_run_and_stays_attributable():
    import cron_main_session_usage_metadata as usage

    job = module.JOB_SPECS["weekly_os_improvement_radar_proof"]
    record = module.dispatch_wake(job, "body", timeout_seconds=10, dry_run=True)
    assert record["dispatched"] is False
    assert record["error_code"] == "dry_run_not_dispatched"
    parsed = usage.parse_cron_run_session_key(record["session_key"])
    assert parsed is not None and parsed[0] == job.job_id


def test_write_paths_cannot_escape_the_workspace():
    module.ensure_workspace_path(module.TMP / "ok.json")
    try:
        module.ensure_workspace_path(Path("C:/Windows/Temp/escape.json"))
    except ValueError:
        return
    raise AssertionError("expected an escaping absolute path to be rejected")


def main() -> int:
    test_every_declared_command_exists_on_disk()
    test_job_ids_are_real_uuids_not_prefixes()
    test_spec_errors_reject_anything_outside_the_declared_script_surface()
    test_a_clean_run_is_ok_and_asks_for_no_reply()
    test_a_failed_step_blocks_and_names_the_command()
    test_a_broken_spec_blocks_before_anything_runs()
    test_validate_rejects_a_widened_or_ungrounded_report()
    test_wake_message_reports_the_failure_without_granting_repair_authority()
    test_dispatch_is_inert_in_dry_run_and_stays_attributable()
    test_write_paths_cannot_escape_the_workspace()
    print("deterministic cron sequence runner tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
