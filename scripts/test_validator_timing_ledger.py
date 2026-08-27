from __future__ import annotations

import validator_timing_ledger as ledger


def _fake_run_command(name: str, command: list[str], timeout: int, dry_run: bool, samples: int = 1) -> dict:
    return {
        "name": name,
        "command": command,
        "elapsed_seconds": 0.1,
        "returncode": 1 if name == "cron_control_packet" else 0,
        "ok": name != "cron_control_packet",
        "failure_kind": "nonzero_returncode" if name == "cron_control_packet" else None,
    }


def test_measured_validator_failure_is_warning_by_default() -> None:
    original = ledger.run_command
    try:
        ledger.run_command = _fake_run_command
        payload = ledger.build_payload("normal", dry_run=False)
    finally:
        ledger.run_command = original
    assert payload["status"] == "warning"
    assert payload["validation"]["status"] == "warning"
    assert payload["validation"]["errors"] == []
    assert "cron_control_packet" in payload["summary"]["measured_validator_failures"]
    assert "measured_validator_failed:cron_control_packet" in payload["validation"]["warnings"]


def test_measured_validator_failure_blocks_in_strict_mode() -> None:
    original = ledger.run_command
    try:
        ledger.run_command = _fake_run_command
        payload = ledger.build_payload("normal", dry_run=False, strict_command_status=True)
    finally:
        ledger.run_command = original
    assert payload["status"] == "blocked"
    assert payload["validation"]["status"] == "blocked"
    assert "cron_control_packet" in payload["validation"]["errors"]


def test_run_command_reports_median_of_samples() -> None:
    timings = [9.0, 1.0, 3.0]
    original = ledger.measure_once
    try:
        ledger.measure_once = lambda name, command, timeout: {
            "name": name,
            "command": command,
            "elapsed_seconds": timings.pop(0),
            "returncode": 0,
            "ok": True,
        }
        result = ledger.run_command("x", ["x"], 10, dry_run=False, samples=3)
    finally:
        ledger.measure_once = original
    assert result["elapsed_seconds"] == 3.0
    assert result["sample_count"] == 3
    assert result["elapsed_min_seconds"] == 1.0
    assert result["elapsed_max_seconds"] == 9.0


def _slow_run_command(name: str, command: list[str], timeout: int, dry_run: bool, samples: int = 1) -> dict:
    return {"name": name, "command": command, "elapsed_seconds": 5.0, "returncode": 0, "ok": True}


def test_single_sample_over_target_is_not_confirmed() -> None:
    original = ledger.run_command
    try:
        ledger.run_command = _slow_run_command
        payload = ledger.build_payload("normal", dry_run=False)
    finally:
        ledger.run_command = original
    summary = payload["summary"]
    assert summary["slow"] is True
    assert summary["over_target_confirmed"] is False
    assert summary["measurement_confidence"] == "single_sample_variance_unbounded"
    assert "profile_elapsed_over_target_single_sample_unconfirmed" in payload["validation"]["warnings"]


def test_multi_sample_over_target_is_confirmed() -> None:
    original = ledger.run_command
    try:
        ledger.run_command = _slow_run_command
        payload = ledger.build_payload("normal", dry_run=False, samples=3)
    finally:
        ledger.run_command = original
    summary = payload["summary"]
    assert summary["over_target_confirmed"] is True
    assert summary["measurement_confidence"] == "median_of_samples"
    assert "profile_elapsed_over_target_single_sample_unconfirmed" not in payload["validation"]["warnings"]


if __name__ == "__main__":
    test_measured_validator_failure_is_warning_by_default()
    test_measured_validator_failure_blocks_in_strict_mode()
    test_run_command_reports_median_of_samples()
    test_single_sample_over_target_is_not_confirmed()
    test_multi_sample_over_target_is_confirmed()
    print("validator_timing_ledger_tests_passed")
