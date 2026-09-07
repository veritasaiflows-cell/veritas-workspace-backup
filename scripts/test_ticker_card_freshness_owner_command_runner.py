#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ticker_card_freshness_owner_command_runner as runner


def test_commands_match_live_agent_turn_payload() -> None:
    """The command chain must mirror the exact live agentTurn payload commands."""
    assert runner.COMMANDS[0] == [
        "python",
        "scripts\\ticker_card_freshness_owner_runner.py",
        "--skip-provider-refresh",
        "--full-answer-mode",
        "changed",
        "--write",
        "--validate",
    ]
    assert runner.COMMANDS[1] == [
        "python",
        "scripts\\trade_grade_os_freshness_cron_runner.py",
        "--component",
        "all",
        "--full-answer-mode",
        "changed",
        "--write",
        "--write-md",
        "--validate",
    ]
    assert runner.COMMANDS[2] == [
        "python",
        "scripts\\pm_control_packet.py",
        "--write",
        "--write-db",
        "--write-compat",
        "--validate",
    ]
    assert runner.COMMANDS[3] == [
        "python",
        "scripts\\cron_control_packet.py",
        "--write",
        "--validate",
    ]
    assert len(runner.COMMANDS) == 4


def test_fail_fast_stops_at_first_failure() -> None:
    calls: list[list[str]] = []

    class FakeProc:
        def __init__(self, returncode: int) -> None:
            self.returncode = returncode
            self.stdout = "out"
            self.stderr = "err"

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return FakeProc(1 if len(calls) == 1 else 0)

    original_run = runner.subprocess.run
    try:
        runner.subprocess.run = fake_run  # type: ignore[assignment]
        results, failed_at = runner.run_commands()
    finally:
        runner.subprocess.run = original_run  # type: ignore[assignment]

    assert failed_at == 1
    assert len(results) == 1
    assert results[0]["exit_code"] == 1
    assert len(calls) == 1, "fail-fast must not run later commands after a failure"


def test_all_steps_pass_produces_ok_proof() -> None:
    class FakeProc:
        returncode = 0
        stdout = "out"
        stderr = ""

    def fake_run(argv, **kwargs):
        return FakeProc()

    original_run = runner.subprocess.run
    try:
        runner.subprocess.run = fake_run  # type: ignore[assignment]
        results, failed_at = runner.run_commands()
    finally:
        runner.subprocess.run = original_run  # type: ignore[assignment]

    assert failed_at == -1
    proof = runner.build_proof(dry_run=False, results=results, failed_at=failed_at)
    assert proof["status"] == "ok"
    assert proof["failed_at_step"] is None
    assert len(proof["results"]) == 4
    assert runner.validate_proof(proof) == []


def test_error_proof_validation_catches_mismatch() -> None:
    class FakeProc:
        returncode = 1
        stdout = "out"
        stderr = "boom"

    def fake_run(argv, **kwargs):
        return FakeProc()

    original_run = runner.subprocess.run
    try:
        runner.subprocess.run = fake_run  # type: ignore[assignment]
        results, failed_at = runner.run_commands()
    finally:
        runner.subprocess.run = original_run  # type: ignore[assignment]

    proof = runner.build_proof(dry_run=False, results=results, failed_at=failed_at)
    assert proof["status"] == "error"
    assert proof["failed_at_step"] == 1
    assert runner.validate_proof(proof) == []


def test_dry_run_proof_structure() -> None:
    proof = runner.build_proof(dry_run=True)
    assert proof["status"] == "dry_run"
    assert proof["dry_run"] is True
    assert len(proof["commands_planned"]) == 4
    assert runner.validate_proof(proof) == []


def test_validate_proof_rejects_forged_ok() -> None:
    forged = runner.build_proof(dry_run=False, results=[], failed_at=-1)
    forged["status"] = "ok"
    errors = runner.validate_proof(forged)
    assert "ok_status_with_failed_or_missing_steps" in errors


def test_timeout_records_failure_without_crash() -> None:
    def fake_run(argv, **kwargs):
        raise runner.subprocess.TimeoutExpired(cmd=argv, timeout=1)

    original_run = runner.subprocess.run
    try:
        runner.subprocess.run = fake_run  # type: ignore[assignment]
        results, failed_at = runner.run_commands()
    finally:
        runner.subprocess.run = original_run  # type: ignore[assignment]

    assert failed_at == 1
    assert results[0]["exit_code"] is None
    assert results[0]["stderr_tail"] == "command timed out"


def main() -> int:
    test_commands_match_live_agent_turn_payload()
    test_fail_fast_stops_at_first_failure()
    test_all_steps_pass_produces_ok_proof()
    test_error_proof_validation_catches_mismatch()
    test_dry_run_proof_structure()
    test_validate_proof_rejects_forged_ok()
    test_timeout_records_failure_without_crash()
    print("ticker_card_freshness_owner_command_runner_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())